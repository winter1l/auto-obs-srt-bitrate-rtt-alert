# auto-obs-srt-bitrate-rtt-alert
auto-obs-srt-bitrate-rtt-alert includes both Korean and English versions  
auto-obs-srt-bitrate-rtt-alert는 한국어, 영어 버전을 지원합니다.

[English](https://github.com/winter1l/auto-obs-srt-bitrate-rtt-alert/tree/main?tab=readme-ov-file#english) | [한국어](https://github.com/winter1l/auto-obs-srt-bitrate-rtt-alert?tab=readme-ov-file#%ED%95%9C%EA%B5%AD%EC%96%B4)

# English
This program is a Python-based script that currently supports only the SRT(LA) server.

The script fetches bitrate and RTT values from the SRT(LA) stats URL. If these values drop below the thresholds specified in abc_config.json, it displays a source in OBS via the OBS WebSocket and then hides it after the specified duration. The script checks bitrate and RTT every 2 seconds, ignoring the first 15 seconds of unstable values to ensure accurate measurement once connected.

Made using GPT 4o, claude 3.5 sonnet.

## How to Use
1. Download `auto-obs-srt-bitrate-rtt-alert_en.zip` from the [Releases.](https://github.com/winter1l/auto-obs-srt-bitrate-rtt-alert/releases)
2. Extract the .zip file and open `abc_config.json` to modify it as needed.
```
Sample code. Do not use this as is.
{
    "STATS_URL": "http://127.0.0.1:8181/stats",  // SRT Server stats URL
    "PUBLISHER": "live/stream/belabox",          // SRT Stream Key
    "OBS_HOST": "localhost",                     // OBS WebSocket IP. Modify this if OBS is running on a different computer.
    "OBS_PORT": 4455,                            // OBS WebSocket port number
    "OBS_PASSWORD": "abc123",                    // OBS WebSocket password
    "SOURCE_NAME": "Low bitrate",                // Name of the OBS source to toggle visibility
    "SCENE_NAME": "Live",                        // Scene name containing the source
    "BITRATE_THRESHOLD": 2000,                   // Display OBS source if bitrate falls below this value (kbps) | Must be greater than 0
    "RTT_THRESHOLD": 700,                        // Display OBS source if RTT exceeds this value (ms) | Must be greater than 0
    "COOLDOWN_SECONDS": 600,                     // Cooldown time after activation (seconds) | Must be longer than SOURCE_DISPLAY_TIME
    "SOURCE_DISPLAY_TIME": 30                    // Duration to display the source (seconds) | Must be longer than 1 second
}
```
3. Run `auto-obs-srt-bitrate-rtt-alert_en.exe`

> [!IMPORTANT]
> `auto-obs-srt-bitrate-rtt-alert_en.exe` and `abc_config.json` must be located in the same folder.
> 
Enjoy!


# 한국어
이 프로그램은 파이썬으로 동작하는 스크립트이며 현재는 SRT(LA) 서버만 지원합니다.

SRT(LA) stats URL에서 비트레이트와 RTT 값을 가져오며 abc_config.json에 설정된 기준 이하로 떨어지면 OBS Websocket을 통해 OBS 소스를 표시한 후 설정한 시간 뒤에 사라지는 스트립트입니다.
2초 마다 비트레이트와 RTT를 감지하며, 연결되었을때 안정적인 측정을 위해 값이 불안정한 처음 15초는 무시하게 됩니다.

GPT 4o, claude 3.5 sonnet를 이용해 만들었습니다.

## 사용방법
1. [Releases](https://github.com/winter1l/auto-obs-srt-bitrate-rtt-alert/releases)에서 `auto-obs-srt-bitrate-rtt-alert_kr.zip`를 받습니다.
2. .zip을 압축 해제하고 `abc_config.json`을 열어 수정합니다.
```
보기용 코드입니다. 이 코드를 사용하지마세요.
{
    "STATS_URL": "http://127.0.0.1:8181/stats",  // SRT Server stats URL
    "PUBLISHER": "live/stream/belabox",          // SRT Stream Key
    "OBS_HOST": "localhost",                     // OBS Websocket IP. 이 파일을 실행하는 컴퓨터와 OBS를 실행하는 컴퓨터가 다르다면 수정
    "OBS_PORT": 4455,                            // OBS Websocket 포트 번호
    "OBS_PASSWORD": "abc123",                    // OBS Websocket 비밀번호
    "SOURCE_NAME": "Low bitrate",                // 보기 상태를 토글할 OBS 소스 이름
    "SCENE_NAME": "Live",                        // 소스가 있는 장면 이름
    "BITRATE_THRESHOLD": 2000,                   // 이 비트레이트 미만이면 OBS 소스를 표시 (kbps) | 0보다 커야함
    "RTT_THRESHOLD": 700,                        // 이 RTT 값 이상이면 OBS 소스를 표시 (ms) | 0보다 커야함
    "COOLDOWN_SECONDS": 600,                     // 작동 후 쿨타임 (초) | SOURCE_DISPLAY_TIME보다 길어야됨
    "SOURCE_DISPLAY_TIME": 30                    // 소스를 표시할 시간 (초) | 1초보다 길어야됨
}
```
3. `auto-obs-srt-bitrate-rtt-alert_kr.exe`를 실행합니다.

> [!IMPORTANT]
> `auto-obs-srt-bitrate-rtt-alert_kr.exe`와 `abc_config.json`은 같은 폴더에 위치해야 합니다.

즐기세요!

# Libraries and Licenses
- [obs-websocket-py](https://github.com/Elektordi/obs-websocket-py)
- [requests](https://github.com/psf/requests)

