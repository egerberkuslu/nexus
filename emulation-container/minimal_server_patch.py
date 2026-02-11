"""
Patch to add MininetCLI support to minimal emulation container server
This can be appended to the minimal server.py
"""

import pty
import os
import select
import termios
import struct
import fcntl
import asyncio

# Add this method to the EmulationServicer class

async def MininetCLI(self, request_iterator, context):
    """
    Streaming bidirectional RPC for Mininet CLI interaction
    """
    import grpc

    # For now, just return an error message since we don't have a running Mininet instance
    # In the minimal stub
    yield emulation_pb2.CLIResponse(error="Mininet CLI not available in minimal emulation mode. Please start a full emulation.")
    return

# To use async server, the serve() function needs to be updated:

async def serve_async():
    server = grpc.aio.server()
    emulation_pb2_grpc.add_EmulationServiceServicer_to_server(
        EmulationServicer(), server
    )
    server.add_insecure_port('[::]:50051')
    await server.start()
    logger.info("✨ Minimal emulation container ready on port 50051")
    await server.wait_for_termination()

# Update __main__ to:
# if __name__ == '__main__':
#     asyncio.run(serve_async())
