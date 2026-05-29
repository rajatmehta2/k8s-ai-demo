#!/bin/sh

# Start socat forwarders in the background to tunnel local host cluster ports
echo "Starting socat port-forwarders..."
socat TCP-LISTEN:49193,fork,bind=127.0.0.1 TCP:host.docker.internal:49193 &
socat TCP-LISTEN:65443,fork,bind=127.0.0.1 TCP:host.docker.internal:65443 &

# Execute the main uvicorn command
echo "Launching Uvicorn server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
