"""
DEFINITIONS
This server handles incoming requests via UART. The transfered commands are
JSONRPC commands (https://www.jsonrpc.org/specification wrapped) into a netstring.
Examples:
    Request: 60:{"method":"set_led_color","id":0,"params":{"rgb":[255,0,0]}},
    Response: 33:{"id":0,"result":{"status":True}},
    
    Request: 60:{"method":"nonsense_func","id":0,"params":{"rgb":[255,0,0]}},
    Response: 43:{"id":0,"error":{"msg":"Unknown method."}},
    48:{"method":"Get_Power_Status","id":7,"params":{}},
"""
import json
import sys
from machine import UART, Pin
from neopixel import NeoPixel
import time

class TimeoutChecker:
    """
    A class that checks if the timeout has expired while waiting for a netstring.
    """
    def __init__(self, timeout_s: float, interval_s: float):
        """
        Constructor.
        :timeout_s: Number of seconds after which the timeout is considered expired.
        :interval_s: Number of seconds between two consecutive checks of the elapsed time.
        """
        self.timeout_s = timeout_s
        self.interval_s = interval_s
        self.last_updated_time = time.time()
        self.start_time = time.time()

    def start_timer(self, timeout_s:int = None):
        # Start the timer.
        self.start_time = time.time()
        # Optionally update the timeout.
        if timeout_s:
            self.timeout_s = timeout_s

    def expired(self) -> bool:
        current_time = time.time()
        if current_time - self.start_time > self.timeout_s:
            return True
        return False

    def elapsed(self) -> float:
        current_time = time.time()
        return current_time - self.start_time
        
    def check_timeout(self) -> None:
        if self.expired():
            raise Exception("Timeout reading netstring.")
        time.sleep(self.interval_s)


class ESP32:
    """
     Constructor. Initializes hardware/connection, e.g. UARTs.
    """
    def __init__(self, baudrate=115200, tx=11, rx=12):
        print("Initialize ESP32")
        self.uart = UART(1, baudrate=baudrate, tx=tx, rx=rx)
        self.timeout_checker = TimeoutChecker(timeout_s=5.0, interval_s=0.2)


    """
    Runs forever in a loop waiting for incoming requests. For each request
    a response is created and send to the caller.
    """
    def blocking_until_data_available(self):
        while True:
            #returns an integer part of readeable data
            num_bytes_to_read = self.uart.any()
            if num_bytes_to_read:
                print("Available UART bytes: {}".format(num_bytes_to_read))
                return
            else:
                time.sleep(0.2)

    def run(self):
        print("Start serving incoming JSONRPC commands.")
        while True:
            # Preset variables to avoid undefined behaviour.
            o_request = {}
            s_response = ""
            request_id = None
            try:
                print("Waiting for JSONRPC commands.")
                # Blocks until netstring is received.
                self.blocking_until_data_available()

                # Reads a complete netstring or raises exception, e.g. on timeout.
                s_request = self.receive_netstring(5.0)
                
                # Take the payload and create the JSON object.
                o_request = self.parse_request(s_request)
                request_id = o_request.get('id', None)
                
                # Interpret the request and call the real handler function.
                o_result = self.handle_request(o_request)

            except Exception as ex:
                print("Exception during JSONRPC handling: " + str(ex))
                s_response = self.create_error_response(str(ex), id=request_id)
                #s_response = self.create_error_response(str(ex))
                
            else: 
                # Create the response in a string representation.
                s_response = self.create_response(o_result, id=request_id)
                
            finally:
                # Send as netstring.
                self.send_netstring(s_response)
        
       
    """
    Blocking function that waits for incoming data. Raises an exception when
    either the received data is not a netstring or when the timeout for
    receiving expired. This function returns the payload of the received 
    netstring, e.g. if the netstring is '11:{"empty":1}' the return value
    will be '{"empty":1}'. 
    :param timeout_s: Timeout inseconds.
    :return: Payload of the received netstring.
    """
    def receive_netstring(self, timeout_s: float):
        # Start timeout with the given value.
        self.timeout_checker.start_timer(timeout_s)

        # Preset variables to avoid undefined behaviour-
        header_str = ""

        # Try to receive the header portion.
        while True:
            # Checks if timeout expired and waits a little time.
            self.timeout_checker.check_timeout()

            # Read the netstring header byte by byte
            header_byte = self.uart.read(1)
            if header_byte is None:
                continue

            header_char = header_byte.decode('ascii')
            if header_char.isdigit():
                header_str += header_char
            elif header_char == ":" and header_str.isdigit():
                # Header is valid if not empty.
                print("JSONRPC header: {0}".format(header_str))
                break
            else:
                # Empty corrupted header
                sys.stderr.write("Header string contains non-digit characters. Flushing {0}\n".format(header_str))
                header_str = ""

        # Parse the netstring header and extract the data length
        data_len = int(header_str)

        # Read the rest of the netstring
        data = b""
        while len(data) < data_len + 1:
            # Check the remaining time.
            self.timeout_checker.check_timeout()

            r = self.uart.read(data_len + 1 - len(data))
            if r is not None:
                data =  data + r
            
        if data[-1] != ord(","):
            raise Exception("Malformed netstring missing trailing comma.")
        data = data[:-1] #remove it

        # Convert bytes to string
        data_str = data.decode('ascii')
        print("JSONRPC payload: {0}".format(data_str))
        return data_str


    """
    Converts the given data and sends it to the caller (e.g. via UART).
    For example the payload string '{"empty":1}' will be converted to
    '11:{"empty":1}' and then sent.
    :param payload: Payload string to be sent as netstring.
    """
    def send_netstring(self, payload:str):
        # Convert the payload to bytes and get its length.
        payload_bytes = payload.encode("ascii")
        length = len(payload_bytes)    
        # Construct the netstring and send it via UART.
        netstring = f"{length}:{payload},".encode("ascii")
        print("Netstring to send over UART: ", netstring)
        self.uart.write(netstring)

 
    """
    Parses the given request to a JSON dictionary. Raises exception if
    conversion cannot be done.
    :param request: String to be parsed as a request.
    :return: JSON dictionary.
    """
    def parse_request(self, request:str) -> dict:
        try:
            request_dict = json.loads(request)
            print("Parsed request:", request_dict)
        except Exception as e:
            raise Exception('Invalid JSONRPC request:', e)
 
        if 'method' not in request_dict:
            raise Exception('Method not specified in JSONRPC request!')
        if not isinstance(request_dict['method'], str):
            raise Exception('Method must be a string! ')
        if 'params' in request_dict and not isinstance(request_dict['params'], (list, dict, type(None))):
            raise Exception('Invalid "params" field in JSONRPC request! ')

        return request_dict

    """
    Checks if the given request is a valid JSONRPC call (https://www.jsonrpc.org/specification).
    If so the specified method is called with the params object as parameters. 
    :param request: Request dictonary, e.g. '{"method":"set_led_color", "params":{"rgb":[255,0,0]}}'.
    :return: Result of the called handler function as JSON dictionary.
    """
    def handle_request(self, request: dict) -> dict:
        # Extract method and params from the JSONRPC request
        print("Request: {}".format(request))
        method = request.get('method', None)
        params = request.get('params', None)

        if not params:
            print("Convert 'None' params to empty dictionary.")
            params = {}

        if not method:
            print(f'Invalid JSONRPC request {request}: method is missing!')
            raise Exception('Invalid JSONRPC request: method is missing!')

        if method not in self.methods:
            raise Exception("Invalid JSONRPC request: method is not found!")

        print("Calling {0} with {1}".format(method, params))
        result = self.methods[method](**params)
        print("Result: {}".format(result))
      
        return result
        
    """
    Converts a JSONRPC response object with given parameters as result object.
    :param response: Response object to be used as 'result' value.
    :return: String representaton of the JSONRPC response.
    response == {"status": True} # from set_led_color e.g.
    create_response => {'id': 0, 'result': {"status": True}}
    """
    def create_response(self, response: dict, id:int) -> str:
        if id:
            response_json = json.dumps({'id': id, 'result': response})
        else:
            response_json = json.dumps({'id': 0, 'result': response})

        print(f"Response: {response_json}")
        return response_json  

    
    """
    Converts error parameters as JSON RPC error response object.
    :param error_msg: Error message.
    :return: String representaton of the JSONRPC error response.
    """
    def create_error_response(self, error_msg:str, id:int) -> str:
        # Create the error response object in str format
        if id:
            error_response = json.dumps({'id': id, 'error': {'message': error_msg, 'code':-1}})
        else:
            error_response = json.dumps({'id': 0, 'error': {'message': error_msg, 'code':-1}})

        print(f'Error response: {error_response}')
        return error_response


if __name__ == '__main__':
    js = ESP32()
    js.run()

