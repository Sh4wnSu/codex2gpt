import importlib.util
import os
import tempfile
import unittest
import uuid
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def load_app_module():
    tempdir = tempfile.TemporaryDirectory()
    original_auth_dir = os.environ.get("LITE_AUTH_DIR")
    os.environ["LITE_AUTH_DIR"] = tempdir.name
    try:
        module_name = f"codex2gpt_app_{uuid.uuid4().hex}"
        spec = importlib.util.spec_from_file_location(module_name, APP_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, tempdir, original_auth_dir
    except Exception:
        tempdir.cleanup()
        if original_auth_dir is None:
            os.environ.pop("LITE_AUTH_DIR", None)
        else:
            os.environ["LITE_AUTH_DIR"] = original_auth_dir
        raise


def restore_auth_dir(tempdir, original_auth_dir):
    tempdir.cleanup()
    if original_auth_dir is None:
        os.environ.pop("LITE_AUTH_DIR", None)
    else:
        os.environ["LITE_AUTH_DIR"] = original_auth_dir


class Codex2GptCompatibilityTests(unittest.TestCase):
    def test_normalize_payload_strips_unsupported_fields(self):
        app, tempdir, original_auth_dir = load_app_module()
        try:
            payload = app.normalize_payload(
                {
                    "model": "gpt-5.4",
                    "input": "hello",
                    "max_output_tokens": 64,
                    "service_tier": "default",
                    "metadata": {"source": "test"},
                    "prompt_cache_key": "session-123",
                }
            )
            self.assertNotIn("max_output_tokens", payload)
            self.assertNotIn("service_tier", payload)
            self.assertNotIn("metadata", payload)
            self.assertEqual(payload["prompt_cache_key"], "session-123")
        finally:
            restore_auth_dir(tempdir, original_auth_dir)

    def test_chat_completion_usage_reports_cache_hits(self):
        app, tempdir, original_auth_dir = load_app_module()
        try:
            completion = app.response_to_chat_completion(
                {
                    "id": "resp_cache_hit",
                    "created_at": 1773667000,
                    "model": "gpt-5.4",
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "OK"}],
                        }
                    ],
                    "usage": {
                        "input_tokens": 120,
                        "output_tokens": 8,
                        "input_tokens_details": {"cached_tokens": 96},
                    },
                }
            )
            self.assertEqual(completion["choices"][0]["message"]["content"], "OK")
            self.assertEqual(completion["usage"]["prompt_tokens"], 120)
            self.assertEqual(completion["usage"]["completion_tokens"], 8)
            self.assertEqual(completion["usage"]["prompt_tokens_details"]["cached_tokens"], 96)
        finally:
            restore_auth_dir(tempdir, original_auth_dir)

    def test_build_responses_payload_from_chat_keeps_prompt_cache_key(self):
        app, tempdir, original_auth_dir = load_app_module()
        try:
            payload = app.build_responses_payload_from_chat(
                {
                    "model": "gpt-5.4",
                    "messages": [
                        {"role": "system", "content": "你是一个助手"},
                        {"role": "user", "content": "只回复OK"},
                    ],
                    "prompt_cache_key": "cache-key-1",
                    "max_tokens": 64,
                    "metadata": {"source": "test"},
                }
            )
            self.assertEqual(payload["instructions"], "你是一个助手")
            self.assertEqual(payload["prompt_cache_key"], "cache-key-1")
            self.assertEqual(payload["input"][0]["role"], "user")
            self.assertNotIn("max_tokens", payload)
            self.assertNotIn("metadata", payload)
        finally:
            restore_auth_dir(tempdir, original_auth_dir)

    def test_chat_completion_usage_chunk_reports_cache_hits(self):
        app, tempdir, original_auth_dir = load_app_module()
        try:
            chunk = app.chat_completion_usage_chunk_from_response(
                {
                    "id": "resp_cache_hit",
                    "created_at": 1773667000,
                    "model": "gpt-5.4",
                    "usage": {
                        "input_tokens": 120,
                        "output_tokens": 8,
                        "input_tokens_details": {"cached_tokens": 96},
                    },
                }
            )
            self.assertEqual(chunk["object"], "chat.completion.chunk")
            self.assertEqual(chunk["choices"], [])
            self.assertEqual(chunk["usage"]["prompt_tokens"], 120)
            self.assertEqual(chunk["usage"]["prompt_tokens_details"]["cached_tokens"], 96)
        finally:
            restore_auth_dir(tempdir, original_auth_dir)

    def test_canonical_json_bytes_match_between_chat_and_responses_payloads(self):
        app, tempdir, original_auth_dir = load_app_module()
        try:
            long_text = "\n".join(
                [f"规则 {i}: 这是一个用于测试 prompt cache 的稳定长上下文，请不要改写。" for i in range(1, 6)]
            )
            responses_payload = app.normalize_payload(
                {
                    "model": "gpt-5.4",
                    "instructions": "你是一个严格遵守指令的助手。只回复 OK。",
                    "input": [
                        {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": long_text + "\n\n最终任务：只回复OK。"}],
                        }
                    ],
                    "prompt_cache_key": "cache-order-test-001",
                    "stream": False,
                }
            )
            responses_payload["stream"] = True
            chat_payload = app.build_responses_payload_from_chat(
                {
                    "model": "gpt-5.4",
                    "messages": [
                        {"role": "system", "content": "你是一个严格遵守指令的助手。只回复 OK。"},
                        {"role": "user", "content": long_text + "\n\n最终任务：只回复OK。"},
                    ],
                    "prompt_cache_key": "cache-order-test-001",
                    "stream": False,
                }
            )
            chat_payload["stream"] = True
            self.assertEqual(app.canonical_json_bytes(responses_payload), app.canonical_json_bytes(chat_payload))
        finally:
            restore_auth_dir(tempdir, original_auth_dir)


if __name__ == "__main__":
    unittest.main()
