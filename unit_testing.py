from unittest import TestCase, main
from json_rpc import ESP32
from json import dumps
import json


class JsonRpcSrv_Test(TestCase):

    json_rpc_srv = None

    def setUp(self) -> None:
        self.json_rpc_srv = ESP32()

class ParseRequestTest(JsonRpcSrv_Test):

   #this class tests the functionality of the "parse_request" method
    #the function parse_request should not require an instantiated object of itself
  

    def test_valid_json(self):
     
       # check Method with a valid json string
      
        o_request_in = {'method': 'test', 'params': {'a': 1, 'b': 2}}
        s_request = dumps(o_request_in)
        o_request_out = self.json_rpc_srv.parse_request(request=s_request)
        self.assertDictEqual(o_request_in, o_request_out)

    def test_invalid_json(self):
      
        #check Method with an invalid json string      
        s_request = '{"method": "test", "params": "a": 1, "b": 2}'
        with self.assertRaises(Exception): 
            self.json_rpc_srv.parse_request(request=s_request) 


class ReceiveNetstringTest(JsonRpcSrv_Test):

    def test_valid_netstring(self):
        self.json_rpc_srv.uart.write(b'1:n,')
        payload = self.json_rpc_srv.receive_netstring(timeout_s=5.0)
        self.assertEqual(payload, 'n')

    def test_valid_netstring_long(self):
        n111 = 'n'* 111
        self.json_rpc_srv.uart.write('111:{},'.format(n111).encode('ascii'))
        payload = self.json_rpc_srv.receive_netstring(timeout_s=5.0)
        self.assertEqual(payload, n111)

    def test_invalid_netstring(self):
        self.json_rpc_srv.uart.write(b'b:a,')
        with self.assertRaises(ValueError):
            self.json_rpc_srv.receive_netstring(timeout_s=5.0)

    def test_timeout(self):
        self.json_rpc_srv.uart.write(b'10:abc')
        with self.assertRaises(TimeoutError):
            self.json_rpc_srv.receive_netstring(timeout_s=1.0) 

    def test_real_example(self):
        self.json_rpc_srv.uart.write(b'60:{"method":"set_led_color","id":0,"params":{"rgb":[255,0,0]}},')
        payload = self.json_rpc_srv.receive_netstring(timeout_s=5.0)
        self.assertEqual(payload, '{"method":"set_led_color","id":0,"params":{"rgb":[255,0,0]}}')


class SendNetstringTest(JsonRpcSrv_Test):

    def test_n111(self):
        n111 = 'n' * 111
        self.json_rpc_srv.send_netstring(payload=n111)
        self.assertEqual(self.json_rpc_srv.uart.buffer, '111:{},'.format(n111))

    def test_empty(self):
        self.json_rpc_srv.send_netstring('{"empty":1}')
        self.assertEqual(self.json_rpc_srv.uart.buffer,  '11:{"empty":1},') 
 


class HandleRequestTest(JsonRpcSrv_Test):

    def test_set_led_valid(self):
        o_request = {"method": "set_led_color", "id": 0, "params": {"rgb": [255, 0, 0]}}
        o_result = self.json_rpc_srv.handle_request(request=o_request)
        self.assertEqual(o_result, {'status': True})
        self.assertEqual(tuple(self.json_rpc_srv.np[0]), (255, 0, 0))

    def test_set_led_valid_w_id(self):
        o_request = {"method": "set_led_color", "id": 1, "params": {"rgb": [255, 0, 0]}}
        o_result = self.json_rpc_srv.handle_request(request=o_request)
        self.assertEqual(o_result, {'status': True,  "id": 1})
        self.assertEqual(tuple(self.json_rpc_srv.np[0]), (255, 0, 0))       

    def test_nonsense_func(self):
        o_request = {"method": "nonsense_func", "id": 0, "params": {"rgb": [255, 0, 0]}},
        with self.assertRaises(Exception):  
            self.json_rpc_srv.handle_request(o_request)

    def test_missing_method(self):
        o_request = {"id": 0, "params": {"rgb": [255, 0, 0]}}
        with self.assertRaises(Exception) as exc:
            self.json_rpc_srv.handle_request(o_request) 


#for the above create_response function fill out the test_create_response_with_id function that tests the create_response function when the response contains id
class CreateResponseTest(JsonRpcSrv_Test):
    def test_create_response_with_id(self):
        response = {'id': 1, 'status': True}
        expected_response = { 'id': 1, 'status': True}
        actual_response = self.json_rpc_srv.create_response(response)
        expected_response_str = json.dumps(expected_response)
        self.assertEqual(actual_response, expected_response_str)

    def test_create_response_with_dict(self):
        response = {'status': True}
        expected_response = {'id': 0, 'result': {'status': True}}
        actual_response = self.json_rpc_srv.create_response(response)
        expected_response_str = json.dumps(expected_response)
        self.assertEqual(actual_response, expected_response_str)

    def test_create_response_with_list(self):
        response = [1, 2, 3]
        expected_response = {'id': 0, 'result': [1, 2, 3]}
        actual_response = self.json_rpc_srv.create_response(response)
        expected_response_str = json.dumps(expected_response)
        self.assertEqual(actual_response, expected_response_str)  


class CreateErrorResponseTest(JsonRpcSrv_Test):

    def test_create_error_response_with_unknown_method(self):
        error_msg = "Unkown method."
        actual_response = self.json_rpc_srv.create_error_response(error_msg)
        expected_response = '{"id": 0, "error": {"msg": "Unkown method."}}'
        self.assertEqual(actual_response, expected_response)

    def test_create_error_response(self):
        error_msg = "Invalid JSONRPC request: method is missing"
        expected_error_response = '{"id": 0, "error": {"msg": "Invalid JSONRPC request: method is missing"}}'
        actual_error_response = self.json_rpc_srv.create_error_response(error_msg)
        self.assertEqual(actual_error_response, expected_error_response) 

if __name__ == '__main__':
    run = main()