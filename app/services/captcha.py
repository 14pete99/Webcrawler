"""CAPTCHA solver integration — 2Captcha and Anti-Captcha APIs."""

from __future__ import annotations

import asyncio

import httpx


class CaptchaSolver:
    """Async CAPTCHA solver supporting 2Captcha and Anti-Captcha."""

    def __init__(self, api_key: str, provider: str = "2captcha") -> None:
        self.api_key = api_key
        self.provider = provider

    async def solve_recaptcha(self, site_key: str, page_url: str) -> str:
        """Submit reCAPTCHA v2 task, poll for result, return token."""
        if self.provider == "2captcha":
            task = {
                "key": self.api_key,
                "method": "userrecaptcha",
                "googlekey": site_key,
                "pageurl": page_url,
                "json": 1,
            }
            return await self._submit_and_poll_2captcha(task)
        else:
            task = {
                "type": "RecaptchaV2TaskProxyless",
                "websiteURL": page_url,
                "websiteKey": site_key,
            }
            return await self._submit_and_poll_anticaptcha(task)

    async def solve_hcaptcha(self, site_key: str, page_url: str) -> str:
        """Submit hCaptcha task, poll for result, return token."""
        if self.provider == "2captcha":
            task = {
                "key": self.api_key,
                "method": "hcaptcha",
                "sitekey": site_key,
                "pageurl": page_url,
                "json": 1,
            }
            return await self._submit_and_poll_2captcha(task)
        else:
            task = {
                "type": "HCaptchaTaskProxyless",
                "websiteURL": page_url,
                "websiteKey": site_key,
            }
            return await self._submit_and_poll_anticaptcha(task)

    async def solve_turnstile(self, site_key: str, page_url: str) -> str:
        """Submit Cloudflare Turnstile task, poll for result, return token."""
        if self.provider == "2captcha":
            task = {
                "key": self.api_key,
                "method": "turnstile",
                "sitekey": site_key,
                "pageurl": page_url,
                "json": 1,
            }
            return await self._submit_and_poll_2captcha(task)
        else:
            task = {
                "type": "TurnstileTaskProxyless",
                "websiteURL": page_url,
                "websiteKey": site_key,
            }
            return await self._submit_and_poll_anticaptcha(task)

    async def solve_image(self, image_b64: str) -> str:
        """Submit image CAPTCHA, poll for result, return answer text."""
        if self.provider == "2captcha":
            task = {
                "key": self.api_key,
                "method": "base64",
                "body": image_b64,
                "json": 1,
            }
            return await self._submit_and_poll_2captcha(task)
        else:
            task = {
                "type": "ImageToTextTask",
                "body": image_b64,
            }
            return await self._submit_and_poll_anticaptcha(task)

    async def _submit_and_poll_2captcha(self, task: dict) -> str:
        """2Captcha: submit task, poll every 5s, max 120s timeout."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post("https://2captcha.com/in.php", data=task)
            data = resp.json()
            if data.get("status") != 1:
                raise RuntimeError(f"2Captcha submit failed: {data}")
            request_id = data["request"]

            for _ in range(24):  # 24 * 5s = 120s
                await asyncio.sleep(5)
                resp = await client.get(
                    "https://2captcha.com/res.php",
                    params={
                        "key": self.api_key,
                        "action": "get",
                        "id": request_id,
                        "json": 1,
                    },
                )
                data = resp.json()
                if data.get("status") == 1:
                    return data["request"]
                if data.get("request") != "CAPCHA_NOT_READY":
                    raise RuntimeError(f"2Captcha error: {data}")

        raise TimeoutError("2Captcha solve timed out after 120s")

    async def _submit_and_poll_anticaptcha(self, task: dict) -> str:
        """Anti-Captcha: submit task, poll every 5s, max 120s timeout."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anti-captcha.com/createTask",
                json={"clientKey": self.api_key, "task": task},
            )
            data = resp.json()
            if data.get("errorId", 1) != 0:
                raise RuntimeError(f"Anti-Captcha submit failed: {data}")
            task_id = data["taskId"]

            for _ in range(24):
                await asyncio.sleep(5)
                resp = await client.post(
                    "https://api.anti-captcha.com/getTaskResult",
                    json={"clientKey": self.api_key, "taskId": task_id},
                )
                data = resp.json()
                if data.get("status") == "ready":
                    solution = data.get("solution", {})
                    return (
                        solution.get("gRecaptchaResponse")
                        or solution.get("token")
                        or solution.get("text")
                        or str(solution)
                    )
                if data.get("errorId", 0) != 0:
                    raise RuntimeError(f"Anti-Captcha error: {data}")

        raise TimeoutError("Anti-Captcha solve timed out after 120s")
