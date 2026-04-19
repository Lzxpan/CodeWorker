import base64
import io
import inspect
import json
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "webui"))

import server  # noqa: E402
from rag.index import index_is_stale, rebuild_index, search_index  # noqa: E402


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def test_no_context_chat_payload():
    payload = server.build_raw_chat_user_message("", "hello")
    assert_true("PINNED FILE CONTENT" not in payload, "empty chat context must not mention pinned files")
    assert_true(payload == "USER QUESTION:\nhello", "empty chat context should be plain user question")


def test_request_max_tokens_clamps_to_default():
    assert_true(server.get_request_max_tokens({}, 128) == 128, "missing maxTokens should use default")
    assert_true(server.get_request_max_tokens({"maxTokens": 32}, 128) == 32, "maxTokens should allow smaller smoke-test budget")
    assert_true(server.get_request_max_tokens({"maxTokens": 9999}, 128) == 128, "maxTokens should not exceed server default")
    assert_true(server.get_request_max_tokens({"maxTokens": "bad"}, 128) == 128, "invalid maxTokens should use default")


def test_default_model_is_gemma4():
    assert_true(server.DEFAULT_MODEL_KEY == "gemma4", "default model should be gemma4")
    assert_true(server.get_models_payload()["defaultModelKey"] == "gemma4", "/api/models defaultModelKey should be gemma4")


def test_gemma_context_window_matches_local_bench():
    assert_true(server.get_model_context_limit("gemma4") == 262144, "gemma4 should default to the selectable 256k context window")
    assert_true(server.get_model_context_limit("qwen35") == 262144, "qwen35 should default to the selectable 256k context window")
    assert_true(any(item["value"] == 262144 for item in server.get_context_options_payload()), "context options should expose 256k")
    assert_true(server.get_chat_max_tokens("gemma4") <= 4096, "gemma4 response budget should leave room for input context")
    limits = server.get_context_limits("gemma4", single_file_focus=False)
    assert_true(limits["total_chars"] >= 20000, "gemma4 RAG char budget should use the selected context window")


def test_gemma_manifest_uses_unsloth_with_mmproj():
    manifest = json.loads((ROOT / "config" / "bootstrap.manifest.json").read_text(encoding="utf-8"))
    gemma = manifest["models"]["gemma4"]
    assert_true(gemma["repo"] == "unsloth/gemma-4-26B-A4B-it-GGUF", "gemma4 must use the Unsloth GGUF repo")
    removed_repo_owner = "bart" + "owski"
    assert_true(removed_repo_owner not in json.dumps(gemma), "gemma4 manifest must not reference the removed GGUF repo owner")
    assert_true(gemma["defaultQuant"] == "UD-Q4_K_M", "gemma4 should default to Unsloth UD-Q4_K_M")
    assert_true(gemma["supportsImages"] is True, "gemma4 should expose image support when mmproj is configured")
    assert_true(gemma["mmprojPatterns"], "gemma4 must require an mmproj file")


def test_model_file_matching_does_not_fallback_on_pattern_miss():
    root = ROOT / ".tmp" / "regression-model-match"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    (root / "gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf").write_bytes(b"fake")
    try:
        from core.models import match_first_model_file

        assert_true(
            match_first_model_file(root, ["*mmproj-BF16*.gguf", "*mmproj-F16*.gguf"]) is None,
            "mmproj lookup must not fall back to the main GGUF file",
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_gemma_multimodal_payload_and_fallback():
    data = "data:image/png;base64," + base64.b64encode(b"fake-png").decode("ascii")
    upload = server.save_uploaded_file("pic.png", "image/png", data)
    original_has_native = server.model_has_native_image_transport
    try:
        server.model_has_native_image_transport = lambda key: False
        content, meta = server.build_attachment_chat_content("", "describe image", [upload], "gemma4")
        messages = server.prepare_messages_for_model("gemma4-local", server.build_raw_messages("gemma4", content, ""))
    finally:
        server.model_has_native_image_transport = original_has_native
    assert_true(meta["nativeImages"] == 0, "gemma4 should not waste time on native image payload without mmproj")
    assert_true(isinstance(messages[0]["content"], str), "gemma4 without mmproj should receive text fallback payload")


def test_image_metadata_fallback_blocks_guessing():
    data = "data:image/png;base64," + base64.b64encode(b"fake-png").decode("ascii")
    upload = server.save_uploaded_file("pic.png", "image/png", data)
    content, meta = server.build_attachment_chat_content("", "describe image", [upload], "gemma4", force_text_fallback=True)
    assert_true(meta["nativeImages"] == 0, "forced fallback should not include native images")
    assert_true(isinstance(content, str), "forced image fallback should produce a text prompt")
    assert_true("不得描述" in content and "不要猜測" in content, "image metadata fallback must explicitly block visual hallucination")


def test_video_metadata_fallback_blocks_guessing():
    upload = {
        "id": "video-1",
        "kind": "video",
        "name": "generated_video.mp4",
        "mimeType": "video/mp4",
        "sizeBytes": 1234,
        "extractionStatus": "video-keyframes-unavailable:ffmpeg-not-found",
        "durationSeconds": 0,
        "keyframeCount": 0,
    }
    block = server.build_attachment_prompt_block([upload], "gemma4")
    assert_true("不得猜測影片畫面" in block, "video metadata-only fallback must block visual guessing")


def test_video_timestamp_selection_handles_short_videos():
    assert_true(server.choose_video_timestamps(None, 3) == [0.1], "unknown duration should still try an early frame")
    short = server.choose_video_timestamps(0.4, 3)
    assert_true(short and short[0] <= 0.35, "short video should use a timestamp inside the clip")
    long = server.choose_video_timestamps(10.0, 3)
    assert_true(len(long) == 3 and long[0] == 0.1 and long[1] == 5.0, "long video should sample beginning/middle/end")
    budget, mode = server.choose_video_keyframe_budget(45.0, 12)
    assert_true(budget == 12 and mode == "balanced", "45s video should use balanced sampled keyframes")
    detailed = server.choose_video_timestamps(45.0, budget)
    assert_true(len(detailed) == 12 and detailed[0] == 0.1, "balanced video should sample more than beginning/middle/end")


def test_media_assessment_exposes_local_limits():
    assessment = server.get_media_analysis_assessment()
    assert_true("recommendedMaxKeyframes" in assessment, "media assessment should expose keyframe budget")
    assert_true("speechToText" in assessment, "media assessment should expose STT backend status")


def test_transcribe_media_attachment_updates_text_preview():
    root = ROOT / ".tmp" / "regression-stt"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    source = root / "audio.wav"
    source.write_bytes(b"fake wav")
    upload = {
        "id": "audio-1",
        "kind": "audio",
        "name": "audio.wav",
        "mimeType": "audio/wav",
        "path": str(source),
        "extractionStatus": "audio-transcript-unavailable",
        "durationSeconds": 0,
        "textPreview": "",
        "textBlocks": [],
    }
    originals = (
        server.ensure_ffmpeg_runtime,
        server.media_has_audio_stream,
        server.get_video_duration_seconds,
        server.extract_media_audio_to_wav,
        server.get_stt_backend_status,
        server.transcribe_wav_with_backend,
    )
    try:
        server.ensure_ffmpeg_runtime = lambda: ("ffmpeg", "ffprobe", "ready")
        server.media_has_audio_stream = lambda source_path, ffprobe: True
        server.get_video_duration_seconds = lambda source_path, ffprobe: 2.5
        server.extract_media_audio_to_wav = lambda source_path, upload_id, ffmpeg: (source, "ready")
        server.get_stt_backend_status = lambda: {"available": True, "backend": "test"}
        server.transcribe_wav_with_backend = lambda wav_path: ("hello transcript", "test-backend")
        server.transcribe_media_attachment(upload)
    finally:
        (
            server.ensure_ffmpeg_runtime,
            server.media_has_audio_stream,
            server.get_video_duration_seconds,
            server.extract_media_audio_to_wav,
            server.get_stt_backend_status,
            server.transcribe_wav_with_backend,
        ) = originals
        shutil.rmtree(root, ignore_errors=True)
    assert_true(upload["textPreview"] == "hello transcript", "STT transcript should become attachment text")
    assert_true(upload["extractionStatus"] == "audio-transcript-extracted:test-backend", "audio extraction status should record STT backend")
    block = server.build_attachment_prompt_block([upload], "gemma4")
    assert_true("hello transcript" in block, "STT transcript should be sent to the model")


def test_history_continuation_uses_previous_answer_tail():
    history = [
        {"role": "user", "content": "請說明架構"},
        {"role": "assistant", "content": "<think>hidden reasoning</think>\n\n第一段答案\n第二段答案"},
    ]
    message = server.build_history_continuation_message("請繼續", history)
    assert_true(message is not None, "continue request should produce a history continuation prompt")
    assert_true("第一段答案" in message and "hidden reasoning" not in message, "continuation should use visible answer text, not reasoning")


def test_chat_messages_include_recent_history():
    history = [
        {"role": "user", "content": "上一題：想更新遊戲速度要怎麼修改？"},
        {"role": "assistant", "content": "<think>internal</think>\n\n請修改 Form1.cs 的 timer.Interval。"},
    ]
    messages = server.build_raw_messages("gemma4", "那上一題的檔案是哪個？", "system prompt", history=history)
    roles = [item["role"] for item in messages]
    assert_true(roles == ["system", "user", "assistant", "user"], "chat messages should include recent user/assistant history before the current user message")
    combined = "\n".join(str(item["content"]) for item in messages)
    assert_true("上一題" in combined and "timer.Interval" in combined, "recent history content should be visible to the model")
    assert_true("internal" not in combined, "history should strip reasoning blocks")


def test_chat_messages_include_compressed_memory_summary():
    summary = "使用者目標 / 待辦:\n- 想調整遊戲速度\n\n已提到檔案 / 符號:\n- Form1.cs\n- gameTimer.Interval"
    messages = server.build_raw_messages(
        "gemma4",
        "上一題要改哪裡？",
        "system prompt",
        history=[],
        memory_summary=summary,
    )
    assert_true(messages[0]["role"] == "system", "compressed memory should be added to the system prompt")
    assert_true("COMPRESSED CONVERSATION MEMORY" in messages[0]["content"], "system prompt should include compressed memory heading")
    assert_true("gameTimer.Interval" in messages[0]["content"], "compressed memory should preserve important implementation references")


def test_compact_session_memory_keeps_ui_history_and_builds_summary():
    old_values = (
        list(server.STATE.history),
        server.STATE.memory_summary,
        server.STATE.memory_compacted_count,
    )
    try:
        with server.STATE_LOCK:
            server.STATE.history = []
            server.STATE.memory_summary = ""
            server.STATE.memory_compacted_count = 0
            for index in range(8):
                server.STATE.history.append({"role": "user", "content": f"第 {index} 題：想更新遊戲速度，請看 Form1.cs"})
                server.STATE.history.append({"role": "assistant", "content": f"第 {index} 答：修改 gameTimer.Interval 與 gameSpeed。"})
            original_len = len(server.STATE.history)
            server.compact_session_memory_locked("gemma4")
            assert_true(len(server.STATE.history) == original_len, "memory compaction should not remove visible UI history")
            assert_true(server.STATE.memory_compacted_count > 0, "memory compaction should record the compacted boundary")
            assert_true("Form1.cs" in server.STATE.memory_summary and "gameTimer.Interval" in server.STATE.memory_summary, "memory summary should preserve important file and symbol references")
    finally:
        with server.STATE_LOCK:
            server.STATE.history, server.STATE.memory_summary, server.STATE.memory_compacted_count = old_values


def test_length_continuation_drops_large_project_context():
    class FakeResponse:
        def __init__(self, lines):
            self.lines = [line.encode("utf-8") for line in lines]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def __iter__(self):
            return iter(self.lines)

    requests = []
    original_urlopen = server.urllib.request.urlopen
    try:
        def fake_urlopen(request, timeout=0):
            payload = json.loads(request.data.decode("utf-8"))
            requests.append(payload)
            if len(requests) == 1:
                return FakeResponse([
                    'data: {"choices":[{"delta":{"content":"first part"},"finish_reason":null}]}\n',
                    'data: {"choices":[{"delta":{},"finish_reason":"length"}]}\n',
                    "data: [DONE]\n",
                ])
            return FakeResponse([
                'data: {"choices":[{"delta":{"content":" second part"},"finish_reason":"stop"}]}\n',
                "data: [DONE]\n",
            ])

        server.urllib.request.urlopen = fake_urlopen
        events = list(server.stream_local_model_events(
            "gemma4-local",
            [
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "PROJECT RAG CONTEXT\n" + ("large context\n" * 200)},
            ],
            timeout_seconds=1,
            max_tokens=16,
            continue_on_length=1,
        ))
    finally:
        server.urllib.request.urlopen = original_urlopen
    assert_true(len(requests) == 2, "length continuation should call the model twice")
    second_messages = requests[1]["messages"]
    second_payload_text = json.dumps(second_messages, ensure_ascii=False)
    assert_true("PROJECT RAG CONTEXT" not in second_payload_text, "length continuation should not resend large project context")
    assert_true("first part" in second_payload_text, "length continuation should include the previous answer tail")
    assert_true(any(event.get("type") == "content" and event.get("text") == " second part" for event in events), "length continuation should stream continued content")


def test_partial_stream_reply_can_be_saved_for_continue():
    old_values = (
        list(server.STATE.history),
        server.STATE.memory_summary,
        server.STATE.memory_compacted_count,
        server.STATE.model_key,
        server.STATE.model_alias,
    )
    try:
        with server.STATE_LOCK:
            server.STATE.history = []
            server.STATE.memory_summary = ""
            server.STATE.memory_compacted_count = 0
            partial = server.build_stream_reply_text("reasoning", "已輸出的部分回答")
            server.append_chat_exchange_locked("gemma4", "請長篇說明", [], "PROJECT RAG CONTEXT", partial, assistant_kind="chat-partial")
            continuation = server.build_history_continuation_message("請繼續", server.STATE.history)
        assert_true(continuation is not None, "partial stream output should be available for manual continue")
        assert_true("已輸出的部分回答" in continuation, "continue prompt should include partial answer tail")
        assert_true("PROJECT RAG CONTEXT" not in continuation, "manual continue should not re-inject full project context")
    finally:
        with server.STATE_LOCK:
            (
                server.STATE.history,
                server.STATE.memory_summary,
                server.STATE.memory_compacted_count,
                server.STATE.model_key,
                server.STATE.model_alias,
            ) = old_values


def test_stream_reasoning_only_length_retries_for_final_answer():
    class FakeResponse:
        def __init__(self, lines):
            self.lines = [line.encode("utf-8") for line in lines]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def __iter__(self):
            return iter(self.lines)

    calls = {"count": 0}
    original_urlopen = server.urllib.request.urlopen
    try:
        def fake_urlopen(_request, timeout=0):
            calls["count"] += 1
            if calls["count"] == 1:
                return FakeResponse([
                    'data: {"choices":[{"delta":{"reasoning_content":"thinking only"},"finish_reason":null}]}\n',
                    'data: {"choices":[{"delta":{},"finish_reason":"length"}]}\n',
                    "data: [DONE]\n",
                ])
            return FakeResponse([
                'data: {"choices":[{"delta":{"content":"final answer"},"finish_reason":"stop"}]}\n',
                "data: [DONE]\n",
            ])

        server.urllib.request.urlopen = fake_urlopen
        events = list(server.stream_local_model_events(
            "gemma4-local",
            [{"role": "user", "content": "hello"}],
            timeout_seconds=1,
            max_tokens=16,
            continue_on_length=1,
        ))
    finally:
        server.urllib.request.urlopen = original_urlopen
    assert_true(calls["count"] == 2, "reasoning-only length response should retry once")
    assert_true(any(event.get("type") == "continuation" and "最終答案" in event.get("text", "") for event in events), "retry should explain answer-only continuation")
    assert_true(any(event.get("type") == "content" and event.get("text") == "final answer" for event in events), "retry should stream final answer content")


def test_gemma_native_image_payload_with_mmproj():
    data = "data:image/png;base64," + base64.b64encode(b"fake-png").decode("ascii")
    upload = server.save_uploaded_file("pic.png", "image/png", data)
    original_has_native = server.model_has_native_image_transport
    try:
        server.model_has_native_image_transport = lambda key: key == "gemma4"
        content, meta = server.build_attachment_chat_content("", "describe image", [upload], "gemma4")
        messages = server.prepare_messages_for_model("gemma4-local", server.build_raw_messages("gemma4", content, ""))
    finally:
        server.model_has_native_image_transport = original_has_native
    assert_true(meta["nativeImages"] == 1, "gemma4 with mmproj should send native image payload")
    assert_true(isinstance(messages[0]["content"], list), "gemma4 native image payload should use OpenAI multimodal content parts")


def test_prepare_attachments_does_not_use_qwen_helper():
    data = "data:image/png;base64," + base64.b64encode(b"fake-png").decode("ascii")
    upload = server.save_uploaded_file("pic.png", "image/png", data)
    original_ensure = server.ensure_local_model_server
    try:
        def fail_if_called(*args, **kwargs):
            raise AssertionError("prepare_attachments_for_model must not start a secondary vision model")

        server.ensure_local_model_server = fail_if_called
        prepared = server.prepare_attachments_for_model("gemma4", [upload])
    finally:
        server.ensure_local_model_server = original_ensure
    assert_true(prepared[0]["id"] == upload["id"], "prepare should preserve original image attachment")
    helper_status = "vision" + "-helper"
    assert_true(helper_status not in str(prepared[0].get("extractionStatus", "")), "prepare should not mark secondary vision status")


def test_stream_attachment_fallback_for_native_model():
    data = "data:image/png;base64," + base64.b64encode(b"fake-png").decode("ascii")
    upload = server.save_uploaded_file("pic.png", "image/png", data)
    original_has_native = server.model_has_native_image_transport
    original_stream = server.stream_local_model_events
    calls = {"count": 0}

    def fake_stream(model_alias, messages, timeout_seconds=180, max_tokens=600, continue_on_length=0):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("Failed to call local model endpoint: HTTP 400: missing mmproj for image_url")
        yield {"type": "content", "text": "fallback ok"}
        yield {"type": "finish", "finishReason": "stop"}

    try:
        server.model_has_native_image_transport = lambda key: True
        server.stream_local_model_events = fake_stream
        events = list(
            server.stream_local_model_with_attachment_fallback(
                "qwen35-local",
                "qwen35",
                "",
                "describe image",
                [upload],
                "",
                max_tokens=32,
                timeout_seconds=5,
                continue_on_length=0,
            )
        )
    finally:
        server.model_has_native_image_transport = original_has_native
        server.stream_local_model_events = original_stream
    assert_true(any(item.get("type") == "attachment_fallback" for item in events), "stream fallback event was not emitted")
    assert_true(any(item.get("text") == "fallback ok" for item in events), "stream fallback did not continue to content")



def test_http_error_body_is_preserved():
    body = io.BytesIO(b'{"error":{"message":"missing mmproj for image_url"}}')
    exc = urllib.error.HTTPError("http://127.0.0.1", 400, "Bad Request", {}, body)
    try:
        server.raise_local_model_http_error(exc)
    except RuntimeError as err:
        assert_true("mmproj" in str(err) and "image_url" in str(err), "HTTPError body must be preserved for fallback detection")
        assert_true(server.is_multimodal_transport_error(err), "preserved HTTPError body should be detected as multimodal error")
    else:
        raise AssertionError("raise_local_model_http_error did not raise")


def test_rag_manifest_search_and_stale():
    root = ROOT / ".tmp" / "regression-project"
    data_dir = ROOT / ".tmp" / "regression-index"
    shutil.rmtree(root, ignore_errors=True)
    shutil.rmtree(data_dir, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    target = root / "main.py"
    target.write_text("import os\n\ndef target_login_flow(user):\n    return user.name\n", encoding="utf-8")
    (root / "notes.md").write_text("# Login\nThe target_login_flow lives in main.py.\n", encoding="utf-8")
    try:
        result = rebuild_index(root, data_dir)
        assert_true(result["files"] == 2, "RAG should index source and docs")
        manifest_path = Path(result["indexDir"]) / "manifest.json"
        assert_true(manifest_path.exists(), "RAG manifest.json was not written")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert_true("sha256" in manifest["files"][0], "RAG manifest must include sha256")
        assert_true(not index_is_stale(root, data_dir), "fresh index should not be stale")
        matches = search_index(root, data_dir, "target_login_flow", limit=3)["matches"]
        assert_true(matches, "RAG search should find target_login_flow")
        assert_true(matches[0]["path"] == "main.py", "RAG search should return the matching path")
        assert_true(matches[0]["lineStart"] >= 1 and matches[0]["lineEnd"] >= matches[0]["lineStart"], "RAG match should include line range")
        target.write_text("import os\n\ndef target_login_flow(user):\n    return user.email\n", encoding="utf-8")
        assert_true(index_is_stale(root, data_dir), "modified file should make index stale")
    finally:
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(data_dir, ignore_errors=True)


def test_rag_model_loading_locator_prefers_source_chunks():
    root = ROOT / ".tmp" / "regression-model-locator"
    data_dir = ROOT / ".tmp" / "regression-model-locator-index"
    shutil.rmtree(root, ignore_errors=True)
    shutil.rmtree(data_dir, ignore_errors=True)
    (root / "webui").mkdir(parents=True, exist_ok=True)
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "runtime" / "WinPython" / "python" / "Lib").mkdir(parents=True, exist_ok=True)
    (root / "data" / "indexes" / "cached").mkdir(parents=True, exist_ok=True)
    (root / "webui" / "server.py").write_text(
        "def ensure_runtime_and_model(model_key):\n"
        "    model_file = resolve_model_file(model_key)\n"
        "    return model_file\n\n"
        "def ensure_local_model_server(model_key):\n"
        "    model_file = ensure_runtime_and_model(model_key)\n"
        "    return launch_llama_server(model_file)\n",
        encoding="utf-8",
    )
    (root / "scripts" / "launch_llama_server.py").write_text(
        "import subprocess\n\n"
        "def launch_llama_server(model_file, mmproj_file=None):\n"
        "    args = ['llama-server', '--model', str(model_file)]\n"
        "    if mmproj_file:\n"
        "        args += ['--mmproj', str(mmproj_file)]\n"
        "    return subprocess.Popen(args)\n",
        encoding="utf-8",
    )
    (root / "scripts" / "start-server.cmd").write_text(
        "@echo off\r\n"
        "set MODEL_FILE=%~1\r\n"
        "llama-server.exe --model \"%MODEL_FILE%\"\r\n",
        encoding="utf-8",
    )
    (root / "config" / "bootstrap.manifest.json").write_text(
        '{"models":{"gemma4":{"repo":"example/gemma","filePatterns":["*.gguf"]}}}',
        encoding="utf-8",
    )
    (root / "docs" / "model-notes.md").write_text(
        "# Model loading\nThis document mentions model loading but is not the implementation.\n",
        encoding="utf-8",
    )
    (root / "runtime" / "WinPython" / "python" / "Lib" / "noise.py").write_text(
        "def ensure_runtime_and_model():\n    return 'do not index bundled runtime'\n",
        encoding="utf-8",
    )
    (root / "data" / "indexes" / "cached" / "manifest.json").write_text(
        '{"summary":"do not index cached RAG output"}',
        encoding="utf-8",
    )
    try:
        result = rebuild_index(root, data_dir)
        assert_true(result["files"] == 5, "RAG should index project source, scripts, config, and docs only")
        matches = search_index(root, data_dir, "請問加載model的code在哪個檔案的哪一段？", limit=5)["matches"]
        assert_true(matches, "model loading locator query should return matches")
        assert_true(
            matches[0]["path"] in {"webui/server.py", "scripts/launch_llama_server.py", "scripts/start-server.cmd"},
            "model loading locator should prefer source code chunks over summaries",
        )
        assert_true(
            "llama-server" in matches[0]["content"] or "ensure_runtime_and_model" in matches[0]["content"],
            "top model loading match should include implementation content",
        )
        assert_true(
            all(not str(item["path"]).startswith(("runtime/", "data/indexes/")) for item in matches),
            "RAG search must not return bundled runtime or cached index files",
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(data_dir, ignore_errors=True)


def test_rag_chinese_game_speed_query_finds_code():
    root = ROOT / ".tmp" / "regression-game-speed"
    data_dir = ROOT / ".tmp" / "regression-game-speed-index"
    shutil.rmtree(root, ignore_errors=True)
    shutil.rmtree(data_dir, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "# Game\n主要遊戲邏輯在 Form1.cs，速度可調整。\n",
        encoding="utf-8",
    )
    (root / "Form1.cs").write_text(
        "using System.Windows.Forms;\n\n"
        "public partial class Form1 : Form {\n"
        "    private Timer gameTimer = new Timer();\n"
        "    private int gameSpeed = 120;\n\n"
        "    private void StartGame() {\n"
        "        gameTimer.Interval = gameSpeed;\n"
        "        gameTimer.Tick += GameLoop;\n"
        "    }\n\n"
        "    private void GameLoop(object sender, System.EventArgs e) {\n"
        "        UpdatePlayer();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    try:
        rebuild_index(root, data_dir)
        matches = search_index(root, data_dir, "想更新遊戲速度要怎麼修改？", limit=3)["matches"]
        assert_true(matches, "Chinese game-speed query should return matches")
        assert_true(matches[0]["path"] == "Form1.cs", "game-speed query should prefer implementation code over README")
        assert_true("gameTimer.Interval" in matches[0]["content"] or "gameSpeed" in matches[0]["content"], "top match should include speed implementation")
    finally:
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(data_dir, ignore_errors=True)


def test_project_rag_context_without_pins():
    root = ROOT / ".tmp" / "regression-chat-project"
    data_dir = ROOT / ".tmp" / "regression-chat-index"
    shutil.rmtree(root, ignore_errors=True)
    shutil.rmtree(data_dir, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    (root / "main.py").write_text("def target_login_flow(user):\n    return user.name\n", encoding="utf-8")
    old_data_dir = server.DATA_DIR
    server.DATA_DIR = data_dir
    try:
        files = server.collect_project_files(root)
        state = server.SessionState(
            project_path=str(root),
            model_key="gemma4",
            model_alias="gemma4-local",
            files=files,
            summary=server.build_summary(root, files, [], []),
            ui_state="ready",
        )
        context, coverage = server.build_project_rag_context(root, state, "target_login_flow 在哪裡", "gemma4")
        assert_true(coverage["mode"] == "project-rag", "chat without pins should use project-rag context")
        assert_true("target_login_flow" in context, "project-rag context should include matching chunk")
    finally:
        server.DATA_DIR = old_data_dir
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(data_dir, ignore_errors=True)


def test_generated_text_file_requires_confirmation():
    root = ROOT / ".tmp" / "regression-generate"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    old_project = server.STATE.project_path
    old_ui = server.STATE.ui_state
    try:
        with server.STATE_LOCK:
            server.STATE.project_path = str(root)
            server.STATE.ui_state = "ready"
        action = server.create_generated_file_preview(
            root,
            {
                "targetPath": "generated/sample.md",
                "title": "sample",
                "content": "# Sample\n\nhello",
            },
        )
        target = root / "generated" / "sample.md"
        assert_true(not target.exists(), "generated file must not be written before confirmation")
        server.confirm_generated_file(str(action["id"]))
        assert_true(target.exists(), "generated file should be written after confirmation")
        assert_true("hello" in target.read_text(encoding="utf-8"), "generated file content should match preview content")
    finally:
        with server.STATE_LOCK:
            server.STATE.project_path = old_project
            server.STATE.ui_state = old_ui
        shutil.rmtree(root, ignore_errors=True)


def test_generation_prompt_infers_multiple_documents_from_previous_answer():
    history = [
        {"role": "user", "content": "請說明功能流程與使用場景"},
        {"role": "assistant", "content": "<think>internal</think>\n\n功能流程：先分析，再產出。\n\n使用場景：報告與簡報。"},
    ]
    requests = server.parse_generation_requests(
        {"prompt": "把剛剛的說明與使用場景做成一個PPTX跟PDF檔"},
        history,
    )
    targets = {item["targetPath"] for item in requests}
    assert_true(any(target.endswith(".pptx") for target in targets), "PPTX request should create a .pptx preview")
    assert_true(any(target.endswith(".pdf") for target in targets), "PDF request should create a .pdf preview")
    assert_true(not any(target.endswith(".md") for target in targets), "multi-format document request must not fall back to .md")
    combined = "\n".join(str(item["content"]) for item in requests)
    assert_true("功能流程" in combined and "internal" not in combined, "generation should use visible previous assistant content")


def test_generation_prompt_infers_excel():
    requests = server.parse_generation_requests({"prompt": "把測試清單做成 Excel 試算表"})
    assert_true(len(requests) == 1, "Excel-only request should create one preview")
    assert_true(requests[0]["targetPath"].endswith(".xlsx"), "Excel request should create an .xlsx target")


def test_generation_word_prompt_uses_previous_answer():
    history = [
        {"role": "user", "content": "請說明 CodeWorker"},
        {"role": "assistant", "content": "<think>hidden</think>\n\nCodeWorker 是本機 AI 助理。"},
    ]
    requests = server.parse_generation_requests({"prompt": "幫我把說明生成word檔"}, history)
    assert_true(requests[0]["targetPath"].endswith(".docx"), "word request should create a .docx target")
    assert_true("CodeWorker 是本機 AI 助理" in requests[0]["content"], "word request should use previous assistant answer")
    assert_true("hidden" not in requests[0]["content"], "word generation should strip reasoning")


def test_generation_with_previous_keyword_is_not_continuation():
    prompt = "請把剛剛的回答生成word檔"
    assert_true(server.is_model_file_generation_request(prompt), "word export prompt should be detected as file generation")
    assert_true(not server.is_history_continuation_request(prompt), "word export prompt must not be treated as continuation")


def test_generation_common_text_aliases():
    cases = {
        "請把剛剛的回答生成txt檔": ".txt",
        "請把剛剛的回答生成純文字檔": ".txt",
        "請把剛剛的回答生成md檔": ".md",
        "請把剛剛的回答生成py檔": ".py",
        "請把剛剛的回答生成js檔": ".js",
        "請把剛剛的回答生成ts檔": ".ts",
        "請把剛剛的回答生成json檔": ".json",
        "請把剛剛的回答生成html檔": ".html",
        "請把剛剛的回答生成css檔": ".css",
        "請把剛剛的回答生成yaml檔": ".yaml",
        "請把剛剛的回答生成sql檔": ".sql",
        "請把剛剛的回答生成cs檔": ".cs",
    }
    history = [{"role": "assistant", "content": "# 測試內容\n\nhello"}]
    for prompt, extension in cases.items():
        assert_true(server.is_model_file_generation_request(prompt), f"{prompt} should be detected as file generation")
        requests = server.parse_generation_requests({"prompt": prompt}, history)
        assert_true(requests[0]["targetPath"].endswith(extension), f"{prompt} should create {extension}")


def test_generated_docx_and_text_previews_can_be_created():
    root = ROOT / ".tmp" / "regression-generate-docx-text"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    old_project = server.STATE.project_path
    old_ui = server.STATE.ui_state
    try:
        with server.STATE_LOCK:
            server.STATE.project_path = str(root)
            server.STATE.ui_state = "ready"
        docx_action = server.create_generated_file_preview(
            root,
            {
                "targetPath": "generated/sample.docx",
                "title": "sample",
                "content": "# Sample\n\nhello",
            },
        )
        text_action = server.create_generated_file_preview(
            root,
            {
                "targetPath": "generated/sample.py",
                "title": "sample",
                "content": "print('hello')\n",
            },
        )
        assert_true(Path(str(docx_action["tempPath"])).exists(), "docx preview should create a temporary docx")
        assert_true(not (root / "generated" / "sample.docx").exists(), "docx preview must not write before confirmation")
        assert_true(str(text_action["content"]).strip() == "print('hello')", "text preview should keep source content")
        assert_true(not (root / "generated" / "sample.py").exists(), "text preview must not write before confirmation")
        docx_result = server.confirm_generated_file(str(docx_action["id"]))
        text_result = server.confirm_generated_file(str(text_action["id"]))
        assert_true((root / "generated" / "sample.docx").exists(), "docx should be written after confirmation")
        assert_true((root / "generated" / "sample.py").read_text(encoding="utf-8").strip() == "print('hello')", "text file should be written after confirmation")
        assert_true(docx_result["exists"] is True and Path(str(docx_result["path"])).exists(), "docx confirm response should prove the file exists")
        assert_true(text_result["exists"] is True and Path(str(text_result["path"])).exists(), "text confirm response should prove the file exists")
        assert_true(int(docx_result["sizeBytes"]) > 0, "docx confirm response should include non-zero size")
        assert_true(str(docx_result["absoluteTargetPath"]).endswith("sample.docx"), "confirm response should include absolute target path")
    finally:
        with server.STATE_LOCK:
            server.STATE.project_path = old_project
            server.STATE.ui_state = old_ui
        shutil.rmtree(root, ignore_errors=True)


def test_inline_docx_generation_uses_pasted_content_without_model():
    prompt = (
        "請把上面的內容生成docx檔給我\n"
        "# CodeWorker 產品說明書\n\n"
        "## 1. 產品概述\n"
        "CodeWorker 是本機 AI 程式碼助理。\n"
    )
    requests = server.build_generation_requests_from_inline_prompt(prompt)
    assert_true(len(requests) == 1, "inline docx request should create one generation request")
    assert_true(requests[0]["targetPath"].endswith(".docx"), "inline docx request should create a .docx target")
    assert_true(requests[0]["title"] == "CodeWorker 產品說明書", "inline docx should use the pasted heading as title")
    assert_true("CodeWorker 是本機 AI 程式碼助理" in requests[0]["content"], "inline docx should use pasted content directly")


def test_previous_answer_docx_generation_uses_history_without_model():
    history = [
        {"role": "user", "content": "請寫產品說明"},
        {
            "role": "assistant",
            "content": "# CodeWorker 產品說明書\n\n## 1. 產品概述\nCodeWorker 是本機 AI 程式碼助理。",
        },
    ]
    prompt = "請把上面的內容生成docx檔給我"
    requests = server.build_generation_requests_without_model(prompt, history)
    assert_true(len(requests) == 1, "previous-answer docx request should create one direct generation request")
    assert_true(requests[0]["targetPath"].endswith(".docx"), "previous-answer docx request should create .docx")
    assert_true(requests[0]["title"] == "CodeWorker 產品說明書", "previous-answer docx should use assistant heading as title")
    assert_true("CodeWorker 是本機 AI 程式碼助理" in requests[0]["content"], "previous-answer docx should use assistant content directly")


def test_generated_pdf_keeps_chinese_text_extractable():
    root = ROOT / ".tmp" / "regression-generate-pdf"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    target = root / "sample.pdf"
    try:
        server.write_pdf(target, "測試文件", "### 標題\n\n您好！我是 CodeWorker。\n\n- 支援 PDF\n- 支援 PPTX")
        from pypdf import PdfReader

        text = "\n".join(page.extract_text() or "" for page in PdfReader(str(target)).pages)
        assert_true("測試文件" in text and "您好" in text, "generated PDF should preserve extractable Chinese text")
        assert_true("ЁН" not in text, "generated PDF should not produce garbled CJK glyph text")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_document_generation_cleans_markdown_for_pptx():
    root = ROOT / ".tmp" / "regression-generate-pptx"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    target = root / "sample.pptx"
    try:
        server.write_pptx(target, "測試簡報", "### 核心功能\n\n- **本機模型**\n- `RAG` 搜尋")
        from pptx import Presentation

        texts = []
        for slide in Presentation(str(target)).slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    texts.append(shape.text)
        combined = "\n".join(texts)
        assert_true("核心功能" in combined and "本機模型" in combined, "PPTX should keep headings and bullets")
        assert_true("**" not in combined and "`" not in combined, "PPTX should not expose raw Markdown markers")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_document_generation_splits_long_pptx_sections():
    root = ROOT / ".tmp" / "regression-generate-pptx-long"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    target = root / "sample.pptx"
    try:
        long_content = "\n".join(f"- 第 {index} 項內容很長，用來確認投影片不會把全部文字塞在同一頁。" for index in range(1, 16))
        server.write_pptx(target, "長內容簡報", long_content)
        from pptx import Presentation

        presentation = Presentation(str(target))
        assert_true(len(presentation.slides) > 2, "long PPTX content should be split across multiple slides")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_model_initiated_generation_uses_model_title_for_filename():
    prompt = "我要生成一個專案功能介紹的PPT文件"
    reply = "# CodeWorker 專案功能介紹\n\n- 本機模型服務\n- 全專案 RAG"
    requests = server.build_generation_requests_from_model_reply(prompt, reply)
    assert_true(len(requests) == 1, "model-initiated PPT request should create one request")
    assert_true(requests[0]["targetPath"].endswith(".pptx"), "PPT request should create a .pptx target")
    assert_true("CodeWorker-專案功能介紹" in requests[0]["targetPath"], "generated filename should come from the model title")
    assert_true("本機模型服務" in requests[0]["content"], "generated content should come from model reply")


def test_generation_system_prompt_is_only_added_for_generation_requests():
    normal_prompt = server.build_chat_system_prompt("gemma4")
    generation_prompt = server.build_chat_system_prompt("gemma4", file_generation_requested=True)
    assert_true("CodeWorker 會在你回答後建立檔案預覽" not in normal_prompt, "normal chat system prompt should not mention file preview")
    assert_true("CodeWorker 會在你回答後建立檔案預覽" in generation_prompt, "generation chat prompt should instruct model to prepare content")


def test_stream_chat_initializes_model_generation_flag():
    source = inspect.getsource(server.WebUIHandler.handle_chat_stream)
    assert_true("file_generation_requested = (" in source, "stream chat must initialize file_generation_requested before preview creation")
    assert_true(
        "build_chat_system_prompt(snapshot.model_key, file_generation_requested=file_generation_requested)" in source,
        "stream chat must pass the generation flag into the model system prompt",
    )


def main():
    tests = [
        test_no_context_chat_payload,
        test_request_max_tokens_clamps_to_default,
        test_default_model_is_gemma4,
        test_gemma_context_window_matches_local_bench,
        test_gemma_manifest_uses_unsloth_with_mmproj,
        test_model_file_matching_does_not_fallback_on_pattern_miss,
        test_http_error_body_is_preserved,
        test_rag_manifest_search_and_stale,
        test_rag_model_loading_locator_prefers_source_chunks,
        test_rag_chinese_game_speed_query_finds_code,
        test_project_rag_context_without_pins,
        test_generated_text_file_requires_confirmation,
        test_generation_prompt_infers_multiple_documents_from_previous_answer,
        test_generation_prompt_infers_excel,
        test_generation_word_prompt_uses_previous_answer,
        test_generation_with_previous_keyword_is_not_continuation,
        test_generation_common_text_aliases,
        test_generated_docx_and_text_previews_can_be_created,
        test_inline_docx_generation_uses_pasted_content_without_model,
        test_previous_answer_docx_generation_uses_history_without_model,
        test_generated_pdf_keeps_chinese_text_extractable,
        test_document_generation_cleans_markdown_for_pptx,
        test_document_generation_splits_long_pptx_sections,
        test_model_initiated_generation_uses_model_title_for_filename,
        test_generation_system_prompt_is_only_added_for_generation_requests,
        test_stream_chat_initializes_model_generation_flag,
        test_gemma_multimodal_payload_and_fallback,
        test_image_metadata_fallback_blocks_guessing,
        test_video_metadata_fallback_blocks_guessing,
        test_video_timestamp_selection_handles_short_videos,
        test_media_assessment_exposes_local_limits,
        test_transcribe_media_attachment_updates_text_preview,
        test_history_continuation_uses_previous_answer_tail,
        test_chat_messages_include_recent_history,
        test_chat_messages_include_compressed_memory_summary,
        test_compact_session_memory_keeps_ui_history_and_builds_summary,
        test_length_continuation_drops_large_project_context,
        test_partial_stream_reply_can_be_saved_for_continue,
        test_stream_reasoning_only_length_retries_for_final_answer,
        test_gemma_native_image_payload_with_mmproj,
        test_prepare_attachments_does_not_use_qwen_helper,
        test_stream_attachment_fallback_for_native_model,
    ]
    try:
        for test in tests:
            test()
            print(f"PASS {test.__name__}")
    finally:
        server.cleanup_image_upload_dir()


def live_gemma_smoke():
    base_url = "http://127.0.0.1:8764"
    if "--base-url" in sys.argv:
        index = sys.argv.index("--base-url")
        if index + 1 < len(sys.argv):
            base_url = sys.argv[index + 1].rstrip("/")
    png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    upload_body = json.dumps(
        {
            "name": "one.png",
            "mimeType": "image/png",
            "data": "data:image/png;base64," + png,
        }
    ).encode("utf-8")
    upload_request = urllib.request.Request(
        f"{base_url}/api/uploads/file",
        data=upload_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(upload_request, timeout=30) as response:
        upload = json.loads(response.read().decode("utf-8"))
    attachment_id = upload["data"]["id"]
    chat_body = json.dumps(
        {
            "message": "請只回答 OK。",
            "modelKey": "gemma4",
            "attachmentIds": [attachment_id],
            "maxTokens": 32,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    chat_request = urllib.request.Request(
        f"{base_url}/api/chat/stream",
        data=chat_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    events = []
    event_payloads = []
    with urllib.request.urlopen(chat_request, timeout=90) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if line.startswith("event:"):
                events.append(line.split(":", 1)[1].strip())
            if line.startswith("data:"):
                event_payloads.append(line.split(":", 1)[1].strip())
            if line == "event: done":
                break
    joined_payloads = "\n".join(event_payloads)
    helper_status = "vision" + "-helper"
    assert_true("qwen35" not in joined_payloads.lower(), "live Gemma4 image smoke must not use a secondary vision model")
    assert_true(helper_status not in joined_payloads.lower(), "live Gemma4 image smoke must not emit secondary vision status")
    assert_true("done" in events, "live Gemma4 image smoke should finish")
    print("PASS live_gemma_smoke")


if __name__ == "__main__":
    if "--live-gemma" in sys.argv:
        live_gemma_smoke()
    else:
        main()
