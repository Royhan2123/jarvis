"""State machine & orkestrasi: IDLE → LISTENING → THINKING → SPEAKING (+ CONFIRMING)."""

from __future__ import annotations

import gc
import queue
import re
import threading
import time
from collections.abc import Callable
from enum import StrEnum

import numpy as np
from loguru import logger

from jarvis import island
from jarvis.approvals import BOARD
from jarvis.audio.sounds import play_confirm, play_done, play_error, play_ting, warm
from jarvis.audio.stream import MicStream
from jarvis.audio.vad import VAD, record_utterance
from jarvis.audio.wakeword import WakeWord, match_any, plausible_wake
from jarvis.brain import rules
from jarvis.brain.actions import ActionRunner
from jarvis.brain.llm import LLM
from jarvis.brain.memory import Memory
from jarvis.brain.router import Plan, Router
from jarvis.brain.rules import Intent, parse_yes_no
from jarvis.config import Config, VADConfig
from jarvis.platform import get_adapter
from jarvis.state_hub import HUB
from jarvis.stt.whisper import WhisperSTT
from jarvis.tools.registry import context, load_tools, registry
from jarvis.tts import TTS, build_tts
from jarvis.tts.stream import SentenceSpeaker, speakable, split_sentences


class State(StrEnum):
    LOADING = "loading"
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    CONFIRMING = "confirming"


def shorten_for_speech(text: str, max_chars: int) -> str:
    """Potong di batas kalimat agar tidak melebihi max_chars."""
    text = speakable(re.sub(r"\s+", " ", text).strip())
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[: end + 1] if end > 0 else cut.rstrip() + "."


class Jarvis:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.state = State.LOADING
        self._voice_feed = island.VoiceFeed(cfg)
        if cfg.audio.sounds:
            warm(cfg.audio.output_device)  # buka stream bunyi lebih dulu: "ting" tanpa jeda
        self.listeners: list[Callable[[State], None]] = []
        self.mic_muted = False
        self._running = False
        self._interrupted = False
        self._speaker: SentenceSpeaker | None = None
        self._monitor: threading.Thread | None = None
        self._monitor_stop = threading.Event()
        self._reminders: queue.Queue[str] = queue.Queue()
        logger.info("Memuat model (wake word, VAD, STT, TTS)…")
        self.memory = Memory(cfg.memory)
        context.configure(get_adapter(cfg), cfg, self.memory)
        load_tools(cfg)
        self.mic = MicStream(cfg.audio)
        self.wake = WakeWord(cfg.wakeword) if cfg.wakeword.engine == "openwakeword" else None
        self.vad = VAD(cfg.vad)
        stt_cfg = cfg.stt
        if (
            cfg.workspace.folders
        ):  # nama file di prompt Whisper → "toko.py" tidak terdengar "topkuo titip"
            from jarvis import workspace

            hint = workspace.stt_hint(cfg)
            stt_cfg = cfg.stt.model_copy(update={"initial_prompt": cfg.stt.initial_prompt + hint})
        # Penyaring wake murah (Whisper tiny); modelnya dibagi dengan pendeteksi bahasa.
        self.gate: WhisperSTT | None = None
        shared_detector = None
        if cfg.wakeword.gate and self.wake is None:
            gate_cfg = cfg.stt.model_copy(
                update={
                    "model": cfg.stt.detect_model,
                    "beam_size": 1,
                    "language": "id",
                    "cpu_threads": cfg.stt.wake_threads,
                }
            )
            self.gate = WhisperSTT(gate_cfg)
            shared_detector = self.gate.model
        self.stt = WhisperSTT(stt_cfg, live=cfg.stt, detector=shared_detector)
        wake_cfg = cfg.stt.model_copy(
            update={
                "model": cfg.stt.wake_model,
                "beam_size": 1,
                "cpu_threads": cfg.stt.wake_threads,
            }
        )
        self.wake_stt = (
            self.stt
            if wake_cfg.model == cfg.stt.model
            else WhisperSTT(wake_cfg, live=cfg.stt, detector=shared_detector)
        )
        self._last_trim = 0.0
        self.llm = LLM(cfg, facts=self.memory.facts_text)
        self.llm.history = self.memory.recent(cfg.llm.history_turns)  # ingat percakapan terakhir
        self.router = Router(cfg)
        self.tts: TTS = build_tts(cfg)
        self.actions = ActionRunner(
            local={"stop_speaking": self._stop_speaking},
            on_error=self._beep_error,
            lang=lambda: self.stt.last_language,
        )
        from jarvis.tools import agent as agent_tool

        agent_tool.confirm_hook, agent_tool.say_hook = self._agent_confirm, self._say
        if (
            cfg.agent.enabled
            and cfg.agent.prewarm
            and cfg.workspace.folders
            and (
                cfg.llm.provider == "ollama"  # pemanasan model online hanya buang kuota
            )
        ):
            threading.Thread(target=self._prewarm_agent, daemon=True).start()
        self._set(State.IDLE)

    def _prewarm_agent(self) -> None:
        try:
            from jarvis.agent import Agent

            t = time.perf_counter()
            Agent(self.cfg, lambda _w: False).warmup()
            logger.info(f"[agen] pemanasan model selesai ({time.perf_counter() - t:.1f}s)")
        except Exception as e:  # noqa: BLE001 — pemanasan gagal tidak boleh mengganggu Jarvis
            logger.warning(f"Pemanasan agen dilewati: {e}")

    # ── util ──
    def _set(self, state: State) -> None:
        self.state = state
        logger.debug(f"state → {state.value}")
        if state is State.SPEAKING and self.cfg.audio.interruptible:
            self._start_monitor()
        HUB.publish(state.value)  # dibaca API lokal (/v1/state)
        self._voice_feed.push(state.value)  # indikator batang suara di pulau Isla
        for fn in self.listeners:
            fn(state)

    def _maybe_trim(self, force: bool = False) -> None:
        """Kembalikan memori bebas ke OS paling sering tiap 30 dtk (mencegah RSS terlihat bocor)."""
        now = time.monotonic()
        if not force and now - self._last_trim < 30:
            return
        self._last_trim = now
        gc.collect()
        try:
            context.adapter.trim_memory()
        except Exception as e:  # noqa: BLE001 — optimasi opsional
            logger.debug(f"trim memori gagal: {e}")

    def _beep_error(self) -> None:
        if self.cfg.audio.sounds:
            play_error(self.cfg.audio.output_device)

    def _stop_speaking(self, _args: dict) -> str:
        self.interrupt()
        return ""

    # ── interupsi saat Jarvis bicara ──
    def interrupt(self) -> None:
        self._interrupted = True
        if self._speaker:
            self._speaker.cancel()
        self.tts.stop()

    def _start_monitor(self) -> None:
        """Selama SPEAKING, dengarkan "berhenti"/kata pemanggil untuk memotong ucapan."""
        if self._monitor and self._monitor.is_alive():
            return
        self._monitor_stop.clear()
        self._monitor = threading.Thread(target=self._monitor_loop, daemon=True, name="interrupt")
        self._monitor.start()

    def _stop_monitor(self) -> None:
        self._monitor_stop.set()
        if (
            self._monitor
            and self._monitor.is_alive()
            and self._monitor is not threading.current_thread()
        ):
            self._monitor.join(timeout=3)
        self._monitor = None

    def _is_interrupt(self, text: str) -> bool:
        if match_any(text, self.cfg.wakeword.all_phrases) is not None:
            return True
        intents = rules.match(text) or []
        return any(i.tool == "stop_speaking" for i in intents)

    def _monitor_loop(self) -> None:
        sr, ms = self.cfg.audio.sample_rate, self.cfg.audio.chunk_ms
        vad = VAD(self.cfg.vad)
        cfg = VADConfig(
            threshold=self.cfg.vad.threshold, silence_ms=400, max_record_s=2, listen_timeout_s=1
        )

        def chunks():
            while not self._monitor_stop.is_set() and self._running:
                yield self.mic.read(timeout=0.3)

        while not self._monitor_stop.is_set() and self._running:
            seg = record_utterance(chunks(), vad.is_speech, cfg, sr, ms)
            # Ucapan pendek yang berakhir karena diam. Segmen yang mentok batas = gema suara
            # Jarvis sendiri (tidak ada pembatalan gema) → abaikan, hemat CPU.
            if (
                seg is None
                or len(seg) < sr * 0.3
                or len(seg) >= sr * cfg.max_record_s - sr * ms // 1000
            ):
                continue
            voiced, ratio = vad.speech_stats(seg)
            if (
                voiced < self.cfg.wakeword.min_speech_s
                or ratio < self.cfg.wakeword.min_speech_ratio
            ):
                continue  # derau/gema, bukan ucapan
            text = self.wake_stt.transcribe(seg, fast=True)
            logger.debug(f"[interupsi?] '{text}'")
            if text and self._is_interrupt(text):
                logger.info("Diinterupsi oleh pengguna")
                self.interrupt()
                return

    def _chunks(self):
        while self._running:
            yield self.mic.read(timeout=0.5)

    def _say(self, text: str, interruptible: bool = True) -> None:
        text = shorten_for_speech(text, self.cfg.tts.max_spoken_chars)
        if not text:
            return
        print(f"{self.cfg.general.name}: {text}")
        self._set(State.SPEAKING)
        if interruptible:
            self._start_monitor()
        try:
            self.tts.speak(text)
        except Exception as e:  # noqa: BLE001 — TTS gagal tidak boleh mematikan app
            logger.error(f"TTS gagal: {e}")
        finally:
            if interruptible:
                self._stop_monitor()

    def _record(self, vad_cfg: VADConfig):
        self.mic.flush()
        self.vad.reset()
        return record_utterance(
            self._chunks(),
            self.vad.is_speech,
            vad_cfg,
            self.cfg.audio.sample_rate,
            self.cfg.audio.chunk_ms,
        )

    def _save_debug_audio(self, audio) -> None:
        """Mode DEBUG: simpan ucapan terakhir (debug/last_utterance.wav) untuk analisis offline."""
        if self.cfg.general.log_level != "DEBUG":
            return
        import wave

        from jarvis.brain.memory import data_dir

        try:
            d = data_dir() / "debug"
            d.mkdir(exist_ok=True)
            with wave.open(str(d / "last_utterance.wav"), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(self.cfg.audio.sample_rate)
                w.writeframes(audio.tobytes())
        except OSError as e:
            logger.debug(f"gagal simpan audio debug: {e}")

    # ── pemrosesan perintah ──
    def handle_utterance(self, audio) -> str | None:
        """STT → router untuk satu ucapan."""
        self._set(State.THINKING)
        t0 = time.perf_counter()
        text = self.stt.transcribe(audio)
        peak = float(np.abs(audio.astype(np.int32)).max()) / 32768 if len(audio) else 0.0
        dur = len(audio) / self.cfg.audio.sample_rate
        logger.info(f"[audio] puncak={peak:.2f} durasi={dur:.1f}s")
        if peak >= 0.97:
            logger.warning("[audio] suara pecah (clipping): kecilkan Input volume mic atau menjauh")
        elif peak < 0.05:
            logger.warning("[audio] suara sangat pelan: dekatkan mic atau naikkan Input volume")
        logger.debug(f"[stt] '{text}' logprob={self.stt.last_logprob:.2f}")
        self._save_debug_audio(audio)
        if not text:
            logger.info("(tidak ada teks terdengar)")
            return None
        if self.stt.is_unclear():
            logger.info(f"[stt] kurang yakin (logprob={self.stt.last_logprob:.2f}): '{text}'")
            self._say("Maaf, kurang jelas. Bisa diulang?")
            self.mic.flush()
            self._set(State.LISTENING)
            retry = self._record(self.cfg.vad)
            if retry is None:
                return None
            self._set(State.THINKING)
            t0 = time.perf_counter()
            text = self.stt.transcribe(retry)
            if not text:
                return None
            logger.info(f"[stt] ulangan: '{text}' (logprob={self.stt.last_logprob:.2f})")
        return self.handle_text(text, t0)

    def handle_text(self, text: str, t0: float | None = None) -> str | None:
        """Router: Tier 0 (aturan) → tool, atau Tier 1/2 (LLM, bicara per kalimat)."""
        self._set(State.THINKING)
        self._interrupted = False
        t0 = t0 or time.perf_counter()
        t_start = time.perf_counter()
        print(f"Kamu: {text}")
        plan = self.router.plan(text)
        logger.debug(f"[router] tier={plan.tier} intents={plan.intents}")
        if plan.intents:
            reply = self.actions.run(plan.intents)
            self._say(reply)
            logger.debug(f"[latency] rule total={time.perf_counter() - t0:.2f}s")
        else:
            docs = self._doc_context(text)
            code = self._file_context(text)
            if not code and self._unresolved_code_request(text):
                reply = self._unresolved_reply()
                self._say(reply)
                self.memory.add_message("user", text)
                self.memory.add_message("assistant", reply)
                return reply
            if code:  # file yang disebut dibaca; konteks lebih besar, tool ubah hanya jika diminta
                docs = f"{docs}\n{code}".strip()
                edit = re.search(
                    r"\b(ubah|ganti|perbaiki|betulkan|tambah\w*|buat\w*)\b", text, re.I
                )
                tools = registry.schemas(["workspace"]) if edit else []
                plan = Plan(
                    model=self.cfg.llm.active_fast_model,
                    tier="fast",
                    tools=[t for t in tools if t["function"]["name"] != "list_files"],
                    num_ctx=self.cfg.workspace.context_num_ctx,
                )
            elif docs:  # dijawab dari dokumen oleh 4B tanpa tools → cepat & tanpa tool-calling
                plan = Plan(model=self.cfg.llm.active_fast_model, tier="fast", tools=[])
            reply = self._ask_llm(text, plan, t0, t_start, docs)
        self.memory.add_message("user", text)
        self.memory.add_message("assistant", reply or "")
        return reply or None

    def _unresolved_code_request(self, text: str) -> bool:
        """Terdengar seperti permintaan soal kode/file, tapi tidak ada file yang cocok."""
        if not self.cfg.workspace.folders:
            return False
        from jarvis import workspace

        return workspace.looks_like_code_request(text)

    def _unresolved_reply(self) -> str:
        from jarvis import workspace

        try:
            names = workspace.list_dir(self.cfg)
        except workspace.WorkspaceError as e:
            return str(e)
        return f"Saya tidak menemukan file yang kamu maksud. {names}"

    def _file_context(self, text: str) -> str:
        """Isi file proyek yang disebut dalam ucapan ("" jika tidak ada / fitur mati)."""
        if not self.cfg.workspace.folders:
            return ""
        try:
            from jarvis import workspace

            return workspace.file_context(self.cfg, text)
        except Exception as e:  # noqa: BLE001 — gagal baca file tidak boleh mematikan jawaban
            logger.warning(f"Konteks file dilewati: {e}")
            return ""

    def _doc_context(self, text: str) -> str:
        """Kutipan dokumen pribadi yang relevan dengan pertanyaan ("" jika tidak ada/mati)."""
        r = self.cfg.rag
        if not (r.enabled and r.auto_context and r.folders) or len(text.split()) < 3:
            return ""
        try:
            from pathlib import Path

            from jarvis.tools.docs import get_index

            t = time.perf_counter()
            hits = [h for h in get_index().search(text) if h.score >= r.min_score]
            logger.debug(
                f"[rag] {len(hits)} kutipan relevan ({time.perf_counter() - t:.2f}s)"
                + (f", terbaik {hits[0].score:.2f}" if hits else "")
            )
        except Exception as e:  # noqa: BLE001 — RAG gagal tidak boleh mematikan jawaban biasa
            logger.warning(f"RAG dilewati: {e}")
            return ""
        return "\n".join(f"[{Path(h.path).name}] {h.text[:500]}" for h in hits)

    def _ask_llm(
        self, text: str, plan: Plan, t0: float, t_start: float, docs: str = ""
    ) -> str | None:
        print(f"{self.cfg.general.name}: ", end="", flush=True)
        speaker = SentenceSpeaker(self.tts, self.cfg.tts.max_spoken_chars)
        self._speaker = speaker
        reply, buf, t_first = "", "", None
        try:
            for piece in self.llm.ask(
                text, model=plan.model, tools=plan.tools, docs=docs, num_ctx=plan.num_ctx
            ):
                if self._interrupted:
                    break
                t_first = t_first or time.perf_counter()
                print(piece, end="", flush=True)
                reply += piece
                buf += piece
                done, buf = split_sentences(buf)
                for sentence in done:
                    self._set(State.SPEAKING)
                    speaker.say(sentence)
        except Exception as e:  # noqa: BLE001
            logger.error(f"LLM gagal ({plan.model}): {e}")
            self._beep_error()
            if plan.tier == "smart":  # 9B belum terpasang / gagal → turun ke 4B
                speaker.finish()
                print()
                fast = self.router.plan("")  # tier fast
                return self._ask_llm(text, fast, t0, t_start, docs)
        print()
        calls = list(self.llm.tool_calls)
        if not any(n == "escalate" for n, _ in calls):
            speaker.say(buf)
        t_llm = time.perf_counter()
        speaker.finish()
        self._speaker = None
        self._stop_monitor()
        t_end = time.perf_counter()
        if self._interrupted:
            return reply.strip() or None
        first = (speaker.first_audio_at or t_end) - t0
        logger.debug(
            f"[latency] tier={plan.tier} llm_first_token={((t_first or t_llm) - t_start):.2f}s "
            f"llm_total={t_llm - t_start:.2f}s mulai_bicara={first:.2f}s total={t_end - t0:.2f}s"
        )
        return self._after_llm(text, plan, reply, calls, t0, t_start)

    def _after_llm(self, text, plan, reply, calls, t0, t_start) -> str | None:
        if any(n == "escalate" for n, _ in calls):
            self._say("Sebentar, saya pikirkan dulu.")
            return self._ask_llm(text, self.router.escalated(text), t0, t_start)
        if calls:
            result = self.actions.run([Intent(n, a) for n, a in calls])
            self.llm.replace_last_reply(result or "(selesai)")
            self._say(result)
            return result or None
        return reply.strip() or None

    def _listen_yes_no(self) -> bool | None:
        """Dengarkan jawaban ya/tidak; diam/tidak jelas = None (diperlakukan batal)."""
        self._set(State.CONFIRMING)
        if self.cfg.audio.sounds:
            play_confirm(self.cfg.audio.output_device)
            time.sleep(0.4)
        v = self.cfg.vad
        vad_cfg = VADConfig(
            threshold=v.threshold,
            silence_ms=600,
            max_record_s=5,
            listen_timeout_s=self.cfg.tools.confirm_timeout_s,
        )
        audio = self._record(vad_cfg)
        heard = self.stt.transcribe(audio) if audio is not None else ""
        logger.info(f"[konfirmasi] terdengar: '{heard}'")
        return parse_yes_no(heard)

    def _confirm_dialog(self) -> None:
        """Tanya ya/tidak untuk tool berisiko; diam/tidak jelas = batal (aman)."""
        self._say(self.actions.resolve(self._listen_yes_no()))

    def _ask_via_island(self, what: str) -> bool | None:
        """Kartu Setuju/Tolak di Isla: True/False bila dijawab; None bila Isla tak bisa dipakai."""
        approval_id = BOARD.request()
        if not island.send_approval(self.cfg, approval_id, f"Jarvis ingin {what}"):
            BOARD.wait(approval_id, 0)  # bersihkan
            return None
        self._say("Saya butuh izin Anda, lihat pulau Isla.", interruptible=False)
        return BOARD.wait(approval_id, self.cfg.island.approval_timeout_s)

    def _agent_confirm(self, what: str) -> bool:
        """Konfirmasi satu langkah agen lewat suara; hanya 'ya' yang jelas yang mengizinkan."""
        print(f"\n⚠️  Agen ingin {what}")
        if self.cfg.ui.api.enabled:
            decision = self._ask_via_island(what)
            if decision is not None:  # Isla menjawab (setuju/tolak/waktu habis): final
                return decision
        island.notify_async(self.cfg, f"Jarvis ingin {what}. Jawab ya atau tidak")
        # tidak boleh diinterupsi: gema suaranya sendiri pernah terdengar sebagai "Hello"
        self._say(f"Saya ingin {what}. Boleh? Bilang ya atau tidak.", interruptible=False)
        return self._listen_yes_no() is True

    # ── wake word ──
    def _wait_wake_phrase(self) -> str | None:
        """Mode frasa: dengarkan ucapan pendek, transkripsi, cocokkan frasa.

        Return sisa ucapan setelah frasa ("" jika hanya frasa), None jika belum terdengar.
        """
        c, v = self.cfg, self.cfg.vad
        short = VADConfig(threshold=v.threshold, silence_ms=400, max_record_s=3, listen_timeout_s=1)
        self.vad.reset()
        seg = record_utterance(
            self._chunks(), self.vad.is_speech, short, c.audio.sample_rate, c.audio.chunk_ms
        )
        if seg is None or len(seg) < c.audio.sample_rate * 0.4:
            return None
        t0 = time.perf_counter()
        w = c.wakeword
        voiced, ratio = self.vad.speech_stats(seg)
        if w.gate and (voiced < w.min_speech_s or ratio < w.min_speech_ratio):
            logger.debug(f"[wake] derau (suara {voiced:.2f}s, {ratio:.0%}) → abaikan")
            return None
        if self.gate is not None:  # tahap 1 murah: mirip kata pemanggil? baru tahap 2 (base)
            heard = self.gate.transcribe(seg, fast=True)
            if not plausible_wake(heard, w.all_phrases):
                logger.debug(f"[wake] gate '{heard}' → abaikan ({time.perf_counter() - t0:.2f}s)")
                return None
        text = self.wake_stt.transcribe(seg, fast=True)
        rest = match_any(text, c.wakeword.all_phrases)
        logger.debug(
            f"[wake] '{text}' → {'COCOK' if rest is not None else 'abaikan'} "
            f"({time.perf_counter() - t0:.2f}s)"
        )
        return rest

    def _reminder_loop(self) -> None:
        mem = Memory(self.cfg.memory, path=self.memory.path)  # koneksi sendiri untuk thread ini
        while self._running:
            for r in mem.due_reminders():
                mem.mark_done(r.id)
                self._reminders.put(r.text)
            time.sleep(3)
        mem.close()

    def _deliver_reminders(self) -> None:
        while not self._reminders.empty():
            text = self._reminders.get()
            logger.info(f"Pengingat: {text}")
            try:
                context.adapter.notify("Pengingat Jarvis", text)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Notifikasi gagal: {e}")
            if self.cfg.audio.sounds:
                play_ting(self.cfg.audio.output_device)
                time.sleep(0.3)
            self._say(f"Pengingat dari {self.cfg.general.user_title}: {text}")
            self.mic.flush()
            self._set(State.IDLE)

    def stop(self) -> None:
        self._running = False

    def set_mic_muted(self, muted: bool) -> None:
        self.mic_muted = muted
        logger.info(f"Mikrofon {'dibisukan' if muted else 'aktif'}")

    def run(self) -> None:
        phrase_mode = self.wake is None
        self._running = True
        threading.Thread(target=self._reminder_loop, daemon=True, name="reminders").start()
        self.mic.start()
        name = " / ".join(self.cfg.wakeword.all_phrases) if phrase_mode else self.cfg.wakeword.model
        print(f'🎙️  Katakan "{name}" (Ctrl+C untuk berhenti)')
        try:
            self._maybe_trim(force=True)  # buang sisa memori pemuatan model
            while self._running:
                self._maybe_trim()
                self._deliver_reminders()
                if self.mic_muted:
                    self.mic.flush()
                    time.sleep(0.2)
                    continue
                remainder = ""
                if phrase_mode:
                    rest = self._wait_wake_phrase()
                    if rest is None:
                        continue
                    remainder = rest
                else:
                    chunk = self.mic.read()
                    if chunk is None or not self.wake.process(chunk):
                        continue
                logger.info("Wake word terdeteksi")
                if self.cfg.audio.sounds:
                    play_ting(self.cfg.audio.output_device)
                    time.sleep(0.25)  # tunggu 'ting' selesai agar tidak terekam mic
                if len(remainder) >= 3:  # perintah diucapkan satu napas: "hello, jam berapa"
                    self.handle_text(remainder)
                else:
                    self._set(State.LISTENING)
                    audio = self._record(self.cfg.vad)
                    if audio is not None:
                        if self.cfg.audio.sounds:
                            play_done(self.cfg.audio.output_device)
                        self.handle_utterance(audio)
                    else:
                        logger.info("Tidak ada suara, kembali idle")
                if self.actions.pending:
                    self._confirm_dialog()
                self.mic.flush()
                if self.wake:
                    self.wake.reset()
                self._set(State.IDLE)
        except KeyboardInterrupt:
            print()
        finally:
            self.mic.stop()


def start_in_thread(
    jarvis_factory: Callable[[], Jarvis], on_ready: Callable[[Jarvis], None]
) -> threading.Thread:
    """Bangun Jarvis (lambat: muat model) lalu jalankan loop di thread terpisah."""

    def target() -> None:
        try:
            j = jarvis_factory()
        except Exception:
            logger.exception("Jarvis gagal dimuat")
            return
        on_ready(j)
        j.run()

    t = threading.Thread(target=target, name="jarvis-loop", daemon=True)
    t.start()
    return t
