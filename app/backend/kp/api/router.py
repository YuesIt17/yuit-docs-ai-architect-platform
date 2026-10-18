"""Aggregate API routers into a single APIRouter."""

from __future__ import annotations

from fastapi import APIRouter

from kp.api import chat, health, jobs, llm, vision

router = APIRouter()
router.include_router(health.router)
router.include_router(llm.router)
router.include_router(chat.router)
router.include_router(vision.router)
router.include_router(jobs.router)
