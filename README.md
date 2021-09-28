# Simple Open Sound Control Recorder and Sequencer

Record osc messages and playback recorded sequence for testing works built with OSC

## Usage

### init

```shell
git clone https://github.com/atsukoba/osc-sequencer.git
cd osc-sequencer
poetry init
# or
pip install -r requirements.txt
 # or manually install dependencies
```

### Record

```text
usage: osc_sequencer.py record [-h] [--ip IP] [--port PORT]
                               [--addresses ADDRESSES [ADDRESSES ...]]
                               [--save_dir SAVE_DIR]
                               [--finish_address FINISH_ADDRESS]
                               [--record_duration RECORD_DURATION] [-V]

optional arguments:
  -h, --help            show this help message and exit
  --ip IP               The ip address to listen on
  --port PORT           The port to listen on
  --addresses ADDRESSES [ADDRESSES ...]
                        The addresses to receive messages
  --save_dir SAVE_DIR   Set directory path to save recorded dump file
  --finish_address FINISH_ADDRESS
                        Set address to trigger stop recording, for example
                        `/finish`
  --record_duration RECORD_DURATION
                        Record duration (sec)
  -V, --verbose         verbose output
```

### PLayback

```text
usage: osc_sequencer.py playback [-h] [--ip IP] [--port PORT] [-V] filepath

positional arguments:
  filepath       File path to record dump JSON data

optional arguments:
  -h, --help     show this help message and exit
  --ip IP        The ip address to listen on
  --port PORT    The port to listen on
  -V, --verbose  verbose output
```

### run example

```shell
cd osc-sequencer/
--> python osc_sequencer.py playback ./data/example.json --port 4000
Sending OSC Messages...:  66%|███████████████████████▊            | 39/59 [00:05<00:02,  6.67it/s]
```
