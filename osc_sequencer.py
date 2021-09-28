import argparse
import json
import logging
import os
import sys
import threading
from datetime import datetime
from logging import debug, info, warn, error
from time import sleep
from typing import Any, Callable, Dict, List, Optional, Tuple

from pythonosc import osc_message, udp_client
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from tqdm import tqdm

TIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"


class Receiver:
    def __init__(self,
                 ip: str,
                 port: int,
                 addresses: List[str],
                 finish_address: Optional[str]):

        # TODO: check if the port is open
        # socket_for_test = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # if socket_for_test.connect_ex((ip, port)) != 0:
        #     socket_for_test.close()
        #     raise NameError("Socket is already used")

        self.ip = ip
        self.port = port
        self.addresses = addresses
        self.stored_data: Dict[str, List[List[str]]] = {}

        if finish_address is not None:
            if finish_address[0] != "/":
                finish_address = "/" + finish_address
            debug(f"finish_address is set: {finish_address}")

        self.finish_address = finish_address
        self.server_thread: Optional[threading.Thread] = None
        self._on_finish: Optional[Callable[[
            Dict[str, List[List[str]]]], None]] = None

    def __get_received_func(
            self, address: str) -> Callable[[str, List[Any]], None]:

        def _on_received(unused_addr: str, *msgs: List[Any]) -> None:
            if self.finish_address:
                debug(
                    f"{address}\tmessages: {msgs}\tunused_addr: {unused_addr}")
            self.stored_data[address].append(
                [str(datetime.now().strftime(TIME_FORMAT)), *map(str, msgs)])

        return _on_received

    def run(self):
        self.dispatcher = Dispatcher()

        for adrs in self.addresses:
            adrs = adrs if adrs[0] == "/" else "/" + adrs
            self.stored_data[adrs] = []
            self.dispatcher.map(adrs, self.__get_received_func(adrs))

        if self.finish_address is not None:
            self.dispatcher.map(self.finish_address, self.finish_wrap)

        self.server = BlockingOSCUDPServer(
            (self.ip, self.port), self.dispatcher)
        debug(f"OSC UDP server is ready and start receiving")
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.setDaemon(True)  # kill when main thread is killed
        self.server_thread.start()
        info(f"Serving on {self.server.server_address}")

    def finish(self):
        if self.server is not None:
            if self._on_finish is not None:
                self._on_finish(self.stored_data)
            sys.exit()
        else:
            warn("finish() called but server (BlockingOSCUDPServer) object is None")

    def finish_wrap(self, unused_addr: str, *args: List[Any]):
        debug("finish() called")
        self.finish()

    def __del__(self):
        if hasattr(self, "server") and self.server is not None:
            self.server.shutdown()


def _get_on_finish_func(save_dir: str) -> Callable[[Dict[str, List[List[str]]]], None]:

    def _on_finish_func(data: Dict[str, List[List[str]]]):
        file_name = f"recorded_{datetime.now().strftime('osc-%Y%m%d-%H%M%S')}.json"
        with open(os.path.join(save_dir, file_name), "w") as f:
            json.dump(data, f)
        debug(f"File saved to : {os.path.join(save_dir, file_name)}")

    return _on_finish_func


def _record(ip: str,
            port: int,
            addresses: List[str],
            save_dir: str,
            record_duration: int,
            finish_address: Optional[str] = None) -> None:

    debug(f"ip: {ip}")
    debug(f"port: {port}")
    debug(f"addresses: {addresses}")
    debug(f"save_dir: {save_dir}")
    debug(f"record_duration: {record_duration}")
    debug(f"finish_address: {finish_address}")

    try:
        recorder = Receiver(ip, port, addresses,
                            finish_address)
    except IOError:
        print("Socket may be already used. Check other process\n")
        print("=" * 40)
        os.system('lsof -i :' + str(port))
        print("=" * 40)
        return

    if finish_address is not None:
        recorder._on_finish = _get_on_finish_func(save_dir)
        recorder.run()
        if recorder.server_thread:
            recorder.server_thread.join()
    else:
        recorder.run()
        for _ in tqdm(range(100), leave=False):
            sleep(record_duration / 100)
        recorder.finish()
        _get_on_finish_func(save_dir)(recorder.stored_data)


def record(args: argparse.Namespace):
    _record(args.ip,
            args.port,
            args.addresses,
            args.save_dir,
            args.record_duration,
            finish_address=args.finish_address)


def _playback(ip: str, port: int, filepath: str):
    assert os.path.exists(filepath), f"file {filepath} not found"

    with open(filepath, "r") as f:
        data = json.load(f)

    time_series_data: List[Tuple[datetime, str, List[str]]] = []
    for address, msg_list in data.items():
        for msgs in msg_list:
            time_series_data.append(
                (datetime.strptime(msgs[0], TIME_FORMAT), str(address), msgs[1:]))

    time_series_data.sort(key=lambda x: x[0])

    client = udp_client.SimpleUDPClient(ip, port)
    debug(f"OSC UDP Client created, address:{ip}, port:{port}")
    finished = False
    current_idx = 0
    stime = datetime.now()
    pbar = tqdm(total=len(time_series_data), desc="Sending OSC Messages...")
    while not finished:
        if current_idx == len(time_series_data):
            finished = True
            break
        if (datetime.now() - stime) > time_series_data[current_idx][0] - time_series_data[0][0]:
            path = time_series_data[current_idx][1]
            data = time_series_data[current_idx][2]
            debug(
                f"{time_series_data[current_idx][1]}\t{' '.join(time_series_data[current_idx][2])}")
            try:
                client.send_message(
                    path,
                    " ".join(data) if data != [] else " ")  # if the data is empty, send white space as message
            except osc_message.ParseError as e:
                error(
                    f"error has occured in the line below\n\n{time_series_data[current_idx]}")
                raise(e)
            except Exception as e:
                raise(e)
            current_idx += 1
            pbar.update(1)
        sleep(0.01)
    pbar.close()
    print("Done!!")
    print(f"{(datetime.now() - stime)} sec")


def playback(args: argparse.Namespace):
    _playback(args.ip, args.port, args.filepath)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Open Sound Control message sequencer')
    subparsers = parser.add_subparsers()

    parser_record = subparsers.add_parser(
        "record", help="Command for recording OSC messages")
    parser_record.add_argument(
        "--ip", type=str, default="127.0.0.1",
        help="The IP address to listen on")
    parser_record.add_argument(
        "--port", type=int, default=5005,
        help="The port to listen on")
    parser_record.add_argument(
        "--addresses", type=str, nargs='+',  default=["/foo", "/bar"],
        help="The addresses to receive messages")
    parser_record.add_argument(
        "--save_dir", type=str, default="./data",
        help="Set directory path to save recorded dump file")
    parser_record.add_argument(
        "--finish_address", type=str, default=None,
        help="Set address to trigger stop recording, for example `/finish`")
    parser_record.add_argument(
        "--record_duration", type=int, default=60,
        help="Record duration (sec)")
    parser_record.add_argument(
        '-V', '--verbose', action='store_true',
        help='verbose output')
    parser_record.set_defaults(handler=record)

    parser_playback = subparsers.add_parser(
        'playback', help='Command for playback recorded OSC messages')
    parser_playback.add_argument(
        "filepath", type=str, help="File path to recorded dump JSON file")
    parser_playback.add_argument(
        "--ip", type=str, default="127.0.0.1",
        help="The IP address to send")
    parser_playback.add_argument(
        "--port", type=int, default=5005,
        help="The port to listen on")
    parser_playback.add_argument(
        '-V', '--verbose', action='store_true',
        help='Verbose output for debugging')
    parser_playback.set_defaults(handler=playback)

    args = parser.parse_args()

    logging.basicConfig(format='%(levelname)s: %(message)s',
                        level=logging.DEBUG if args.verbose else logging.INFO)

    if hasattr(args, 'handler'):
        args.handler(args)
    else:
        parser.print_help()
