# JSON-RPC
This is a simple JSON-RPC server implementation for MicroPython. It uses UART communication to receive JSON-RPC requests and send back responses.

## Features
- Handles requests and responses as netstrings over UART
- Includes request parsing, method routing, and response creation
- Handles request timeouts and malformed requests

## Usage
To use the server:

- Import the ESP32 class
- Incluede the desired UART parameters
- Implement handler methods for each supported RPC method
- Call run() to start the server loop
- The ESP32 handles receiving requests as netstrings over UART, parsing them, routing to the correct handler method, and sending back responses.

Handlers just need to implement the RPC method logic and return a result.


## Implementation Details
- TimeoutChecker - Helper class to track timeouts when reading netstrings
- receive_netstring() - Reads a complete netstring from the UART
- send_netstring() - Sends a netstring payload over UART
- parse_request() - Parses the JSON-RPC request object from a string
- handle_request() - Looks up and calls the handler for the requested method
- create_response() - Creates a JSON-RPC response object as a string