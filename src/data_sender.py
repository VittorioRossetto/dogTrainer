# # data_sender.py
# import json
# import socket
# import time
# from threading import Thread, Event

# class DataSender(Thread):
#     """
#     Connects to host_ip:host_port and sends JSON events.
#     Accepts put_event(event_dict) which pushes into an internal queue.
#     """
#     def __init__(self, host_ip="192.168.1.100", host_port=9000, reconnect_interval=5):
#         super().__init__(daemon=True)
#         self.host = host_ip
#         self.port = host_port
#         self.reconnect_interval = reconnect_interval
#         self.sock = None
#         self._queue = []
#         self._stopped = Event()

#     def put_event(self, ev):
#         self._queue.append(ev)

#     def _connect(self):
#         try:
#             self.sock = socket.create_connection((self.host, self.port), timeout=5)
#             return True
#         except Exception as e:
#             self.sock = None
#             return False

#     def run(self):
#         while not self._stopped.is_set():
#             if not self.sock:
#                 ok = self._connect()
#                 if not ok:
#                     time.sleep(self.reconnect_interval)
#                     continue
#             if self._queue:
#                 ev = self._queue.pop(0)
#                 try:
#                     data = json.dumps(ev) + "\n"
#                     self.sock.sendall(data.encode("utf-8"))
#                 except Exception as e:
#                     print("[data_sender] send failed, reconnecting:", e)
#                     try:
#                         self.sock.close()
#                     except:
#                         pass
#                     self.sock = None
#             else:
#                 time.sleep(0.1)

#     def stop(self):
#         self._stopped.set()
#         try:
#             if self.sock:
#                 self.sock.close()
#         except:
#             pass
