"""The voice bridge: a browser call channel for KIRRO (ADR-016).

A user talks to the "Kirro Declare" agent from a web page. Audio never touches a phone network: the
browser captures the microphone, this service streams it to Gnani for speech-to-text, drives the
agent over AgenticOrg's chat API with the resulting text, and streams Gnani's text-to-speech reply
back to the same browser tab.

This service holds no state and makes no decisions — it is a relay. Every business decision stays
with the agent on AgenticOrg (ADR-011).
"""
