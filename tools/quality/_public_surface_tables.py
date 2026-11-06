"""Encoded tables for the public-surface guard.

The guard catches terms that the public tree must not carry, and a file that
spells those terms out in plain text can never pass a scan of the tree it lives
in. They are therefore stored here as base64 of a JSON document, and the guard
decodes them at import time. Decode either table to read it:

    python -c "import base64, tools.quality._public_surface_tables as t; \
print(base64.b64decode(t.FORBIDDEN_B64).decode())"

Each entry of the forbidden table carries a label, a regular expression and its
flags. Each entry of the probe table carries a label, a string the matching
pattern must accept and a near-miss it must reject, so the guard's tests prove
that every screen still has teeth without restating what it screens for.

This module is generated, not hand-edited. The generator lives outside the
repository so that the plain-text source of these terms stays out of it.
"""

from __future__ import annotations

#: Screen 1: what the public surface must not carry.
FORBIDDEN_B64 = (
    "WwogewogICJmbGFncyI6IDIsCiAgImxhYmVsIjogImEgdmVuZG9yIG9yIHByb2R1Y3QgbmFt"
    "ZSBmb3IgYSBob3N0ZWQgbGFuZ3VhZ2Ugc2VydmljZSIsCiAgInBhdHRlcm4iOiAiXFxiKD86"
    "Q2hhdEdQVHxPcGVuQUl8QW50aHJvcGljfENsYXVkZXxDb2RleHxEZWVwU2Vla3xDb3BpbG90"
    "fEdlbWluaXxMbGFtYXxNaXN0cmFsfEdyb2t8UXdlbnxLaW1pfFBlcnBsZXhpdHl8T2xsYW1h"
    "KVxcYiIKIH0sCiB7CiAgImZsYWdzIjogMiwKICAibGFiZWwiOiAiYSBuYW1lIGZvciBvbmUg"
    "aG9zdGVkIHJlYXNvbmluZyBtb2RlbCIsCiAgInBhdHRlcm4iOiAiXFxiKD86R1BULVswLTld"
    "KD86XFwuWzAtOV0rKT98VGVycmEgKD86TWVkaXVtfEhpZ2gpfFNvbCBIaWdofEx1bmEgTWVk"
    "aXVtfGNsYXVkZS1bYS16MC05XVthLXowLTkuLV0qKVxcYiIKIH0sCiB7CiAgImZsYWdzIjog"
    "MCwKICAibGFiZWwiOiAiYW4gYWJicmV2aWF0aW9uIG5hbWluZyB0aGF0IHRlY2hub2xvZ3ki"
    "LAogICJwYXR0ZXJuIjogIlxcYig/OkxMTXM/fEFHSSlcXGIiCiB9LAogewogICJmbGFncyI6"
    "IDAsCiAgImxhYmVsIjogInRoYXQgYWJicmV2aWF0aW9uIHVzZWQgYXMgYSBkZXZlbG9wbWVu"
    "dCB0b29sIiwKICAicGF0dGVybiI6ICIoPzwhW0EtWmEtejAtOV9dKUFJKD8hW0EtWmEtejAt"
    "OV0pIgogfSwKIHsKICAiZmxhZ3MiOiAyLAogICJsYWJlbCI6ICJ0aGF0IGFiYnJldmlhdGlv"
    "biB3aXRoIGFuIGFzc2lzdGFuY2Ugc3VmZml4IiwKICAicGF0dGVybiI6ICJBSVtcXHMtXSoo"
    "Pzphc3Npc3RlZHxnZW5lcmF0ZWR8d3JpdHRlbnxhdXRob3JlZHxwb3dlcmVkfGRyaXZlbiki"
    "CiB9LAogewogICJmbGFncyI6IDIsCiAgImxhYmVsIjogIm9yY2hlc3RyYXRpb24gdm9jYWJ1"
    "bGFyeSIsCiAgInBhdHRlcm4iOiAiKD88IVtBLVphLXowLTlfXSkoPzpzdWItP2FnZW50cz98"
    "YWdlbnRpY3xtdWx0aS0/YWdlbnR8b3JjaGVzdHJhdG9ycz8pKD8hW0EtWmEtejAtOV0pIgog"
    "fSwKIHsKICAiZmxhZ3MiOiAyLAogICJsYWJlbCI6ICJhbiBhZ2VudCB1c2VkIGFzIGEgd29y"
    "a2Zsb3cgdGVybSIsCiAgInBhdHRlcm4iOiAiKD88IXVzZXItKSg/PCF1c2VyIClcXGJhZ2Vu"
    "dHM/XFxiKD8hXFwubWQpIgogfSwKIHsKICAiZmxhZ3MiOiAyLAogICJsYWJlbCI6ICJpbnN0"
    "cnVjdGlvbi10ZXh0IGphcmdvbiIsCiAgInBhdHRlcm4iOiAiKD86XFxicHJvbXB0cz9bL1xc"
    "XFxdfFxcYltcXHctXStcXC5wcm9tcHRcXGJ8XFxibmV4dC1wcm9tcHRcXGJ8XFxiKD86c3lz"
    "dGVtfGJvb3RzdHJhcHxpbmplY3Rpb258aW5zdHJ1Y3Rpb258cmV2aWV3fGJhc2V8ZGF0YXxp"
    "bml0aWFsKVxccytwcm9tcHRzP1xcYnxcXGJwcm9tcHRcXHMrKD86ZmlsZXx0ZW1wbGF0ZXx0"
    "ZXh0fGluamVjdGlvbnxjaGFpbnxsaWJyYXJ5KVxcYikiCiB9LAogewogICJmbGFncyI6IDIs"
    "CiAgImxhYmVsIjogImEgcHJpdmF0ZSB3b3JrZmxvdyBhcnRpZmFjdCBuYW1lIiwKICAicGF0"
    "dGVybiI6ICIoPzpcXGJBR0VOVFMoPzpfWzAtOV0pP1xcLm1kXFxifFxcYkNMQVVERVxcLm1k"
    "XFxifFxcLmNsYXVkZVxcYnxcXC5hZ2VudHNcXGJ8XFwub3BlbmNvZGVcXGJ8XFxiaGFuZG9m"
    "ZnM/L3xcXGJTVEFURVxcLm1kXFxifFxcYkNVUlJFTlRcXC5tZFxcYnxcXGJSRVZJRVdfVEVN"
    "UExBVEVcXC5tZFxcYnxcXGJtaWdyYXRpb25cXC50eHRcXGJ8XFxiU0tJTExcXC5tZFxcYnx0"
    "b29scy9hZ2VudF9za2lsbHN8XFxiemZsb3dcXGJ8cmV2aWV3LWxvZzF8Y2xhdWRlXyg/Omxv"
    "Y2FsfGNsb3VkKVxcYnxsb2NhbF9oZWFkbGVzc1xcYikiCiB9LAogewogICJmbGFncyI6IDIs"
    "CiAgImxhYmVsIjogInNlc3Npb24tbGlmZWN5Y2xlIHZvY2FidWxhcnkiLAogICJwYXR0ZXJu"
    "IjogIlxcYnNlc3Npb25zP1tcXHMtXSsoPzpub3Rlcz98b3JjaGVzdHJhdGlvbnxtYW5hZ2Vt"
    "ZW50fGxvZ3xoYW5kb2ZmfHRyYW5zY3JpcHQpcz9cXGIiCiB9LAogewogICJmbGFncyI6IDAs"
    "CiAgImxhYmVsIjogImEgbWFjaGluZS1zcGVjaWZpYyBhYnNvbHV0ZSBwYXRoIiwKICAicGF0"
    "dGVybiI6ICIoPzpbQS1aYS16XTpbXFxcXC9dKyg/OlVzZXJzfERldnx0bXB8VGVtcCkoPzpb"
    "XFxcXC9dK3woPyFbQS1aYS16MC05XSkpfCVURU1QJXwlTE9DQUxBUFBEQVRBJXxweXRlc3Qt"
    "b2YtW0EtWmEtejAtOS5fLV0rfC9ob21lL1thLXpdW2EtejAtOV8tXSovfFxcXFxcXFxcW0Et"
    "WmEtejAtOS5fJC1dK1xcXFxbQS1aYS16MC05Ll8kLV0rKSIKIH0sCiB7CiAgImZsYWdzIjog"
    "MCwKICAibGFiZWwiOiAiYW4gZW1iZWRkZWQgY3JlZGVudGlhbCIsCiAgInBhdHRlcm4iOiAi"
    "KD86c2stW0EtWmEtejAtOV8tXXsyMCx9fGdpdGh1Yl9wYXRfW0EtWmEtejAtOV9dezIwLH18"
    "Z2hwX1tBLVphLXowLTldezIwLH18Z2xwYXQtW0EtWmEtejAtOV8tXXsxNix9fEFLSUFbMC05"
    "QS1aXXsxNn0pIgogfSwKIHsKICAiZmxhZ3MiOiAwLAogICJsYWJlbCI6ICJtYWxmb3JtZWQg"
    "dGV4dCBsZWZ0IGJ5IGEgbWVjaGFuaWNhbCBzdWJzdGl0dXRpb24iLAogICJwYXR0ZXJuIjog"
    "Iig/OnRoZSByZXZpZXcgam9ifGZvbGRlZCBpbnRvIGl0cyBzdWNjZXNzb3IpIgogfSwKIHsK"
    "ICAiZmxhZ3MiOiAyLAogICJsYWJlbCI6ICJkZXZlbG9wbWVudC1zZXNzaW9uIGhhbmRvZmYg"
    "dm9jYWJ1bGFyeSIsCiAgInBhdHRlcm4iOiAiXFxiKD86c2Vzc2lvbnM/fGFnZW50cz98ZGV2"
    "ZWxvcGVycz8pW1xccy1dK2hhbmRvZmZzP1xcYnxcXGJIQU5ET0ZGIFBPSU5UXFxifGhhbmRv"
    "ZmZcXHMrKD86ZG9jdW1lbnR8bm90ZXxkaXJlY3Rvcnl8ZmlsZSlzP1xcYiIKIH0KXQ=="
)

#: Screen 2: positive and negative controls, one pair per forbidden entry.
PROBES_B64 = (
    "WwogWwogICJhIHZlbmRvciBvciBwcm9kdWN0IG5hbWUgZm9yIGEgaG9zdGVkIGxhbmd1YWdl"
    "IHNlcnZpY2UiLAogICJwYWlyIHJldmlld2VkIHdpdGggQ2xhdWRlIG9uIHRoZSBicmFuY2gi"
    "LAogICJDbGF1ZGV0dGUgbWFpbnRhaW5lZCB0aGUgcGFyc2VyIgogXSwKIFsKICAiYSBuYW1l"
    "IGZvciBvbmUgaG9zdGVkIHJlYXNvbmluZyBtb2RlbCIsCiAgInRoZSBHUFQtNS42IGxhcmdl"
    "LWNvbnRleHQgcGFzcyIsCiAgInRoZSBHUFRRIHF1YW50aXNlciIKIF0sCiBbCiAgImFuIGFi"
    "YnJldmlhdGlvbiBuYW1pbmcgdGhhdCB0ZWNobm9sb2d5IiwKICAiYW4gTExNIHdyb3RlIHRo"
    "ZSBzdW1tYXJ5IiwKICAiTExNWCBpcyBhIGZpbGUgZm9ybWF0IgogXSwKIFsKICAidGhhdCBh"
    "YmJyZXZpYXRpb24gdXNlZCBhcyBhIGRldmVsb3BtZW50IHRvb2wiLAogICJBSSByZXZpZXdl"
    "ZCB0aGUgY2hhbmdlIiwKICAiQUlNIGlzIHRoZSB0YXJnZXRpbmcgbW9kZSIKIF0sCiBbCiAg"
    "InRoYXQgYWJicmV2aWF0aW9uIHdpdGggYW4gYXNzaXN0YW5jZSBzdWZmaXgiLAogICJhbiBB"
    "SS1hc3Npc3RlZCB0cmFuc2NyaXB0aW9uIiwKICAiYW4gYWlkLWFzc2lzdGVkIHRyYW5zY3Jp"
    "cHRpb24iCiBdLAogWwogICJvcmNoZXN0cmF0aW9uIHZvY2FidWxhcnkiLAogICJ0aGUgc3Vi"
    "YWdlbnQgcmV0dXJuZWQgZWFybHkiLAogICJ0aGUgc3ViYXNzZW1ibHkgd2FzIHJlbW92ZWQi"
    "CiBdLAogWwogICJhbiBhZ2VudCB1c2VkIGFzIGEgd29ya2Zsb3cgdGVybSIsCiAgInRoZSBh"
    "Z2VudCBmaWxlZCB0aGUgcmVwb3J0IiwKICAidGhlIHJlYWdlbnQgd2FzIGNvbnN1bWVkOyBV"
    "c2VyLWFnZW50OiAqIGFsbG93cyBldmVyeSBjcmF3bGVyIgogXSwKIFsKICAiaW5zdHJ1Y3Rp"
    "b24tdGV4dCBqYXJnb24iLAogICJwYXN0ZSB0aGlzIGludG8gdGhlIGJvb3RzdHJhcCBwcm9t"
    "cHQiLAogICJ0aGUgcmVwbHkgY2FtZSBwcm9tcHRseSBmcm9tIHRoZSBTY3JpcHRpbmcgcHJv"
    "bXB0IGNvbnRyb2wiCiBdLAogWwogICJhIHByaXZhdGUgd29ya2Zsb3cgYXJ0aWZhY3QgbmFt"
    "ZSIsCiAgInNlZSBBR0VOVFMubWQgZm9yIHRoZSBydWxlcyIsCiAgInNlZSBNWUFHRU5UUy5t"
    "ZCBmb3IgdGhlIHJ1bGVzIgogXSwKIFsKICAic2Vzc2lvbi1saWZlY3ljbGUgdm9jYWJ1bGFy"
    "eSIsCiAgInRoZSBzZXNzaW9uIHRyYW5zY3JpcHQgd2FzIGF0dGFjaGVkIiwKICAidGhlIHNl"
    "c3Npb24gc3RhdGUgd2FzIHJlbG9hZGVkIgogXSwKIFsKICAiYSBtYWNoaW5lLXNwZWNpZmlj"
    "IGFic29sdXRlIHBhdGgiLAogICJyZWFkIEM6XFxVc2Vyc1xcc29tZW9uZVxccHJvamVjdFxc"
    "ZmlsZS50eHQgb3IgQzpcXHRtcFxudGhlbiBzdG9wIiwKICAiVXNlcnMgYXJlIGxpc3RlZCBp"
    "biB0aGUgbWFudWFsOyBDOlxcdGVtcGxhdGUgaXMgYSBmb2xkZXIgbmFtZSIKIF0sCiBbCiAg"
    "ImFuIGVtYmVkZGVkIGNyZWRlbnRpYWwiLAogICJ0aGUga2V5IHNrLWFiY2RlZmdoaWprbG1u"
    "b3BxcnN0dXZ3eCB3YXMgcm90YXRlZCIsCiAgInRoZSBrZXkgc2stc2hvcnQgd2FzIHJvdGF0"
    "ZWQiCiBdLAogWwogICJtYWxmb3JtZWQgdGV4dCBsZWZ0IGJ5IGEgbWVjaGFuaWNhbCBzdWJz"
    "dGl0dXRpb24iLAogICJKb2IgYHRoZSByZXZpZXcgam9iYCwgbG9jYWwgc2Vzc2lvbiIsCiAg"
    "InRoZSByZXZpZXcgd2FzIHRob3JvdWdoIGFuZCB0aGUgam9iIGZpbmlzaGVkIgogXSwKIFsK"
    "ICAiZGV2ZWxvcG1lbnQtc2Vzc2lvbiBoYW5kb2ZmIHZvY2FidWxhcnkiLAogICJhdHRhY2gg"
    "dGhlIHNlc3Npb24gaGFuZG9mZiBkb2N1bWVudCIsCiAgInJlY29yZGVkIGFzIGEgaGFuZG9m"
    "ZiB0byB0aGUgbmV4dCByZXNlYXJjaCBwYXNzIgogXQpd"
)
