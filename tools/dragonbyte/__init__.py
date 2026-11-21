"""The session, journal and edit library under the DragonByte Z application.

A session over a verified image and an authored project, the undo journal, and
the typed edits for text, data, maps, graphics and raw bytes. No module here
imports Qt. The application that presents this library is ``tools/creator``.

The SDK stays the only authority on ROM content; this package holds no format
constant, address or record stride of its own, and the shipping package under
``tools/webfoot`` must never import this one.
"""
