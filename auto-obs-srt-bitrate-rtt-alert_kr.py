"""
auto-obs-srt-bitrate-rtt-alert_kr v1.0.0

이 프로그램은 SRT 서버의 비트레이트와 RTT(Round Trip Time)를 모니터링하고, 
설정값 이하/이상으로 떨어질/올라갈 경우 OBS의 특정 장면 속 소스를 자동으로 표시/숨김 처리합니다.

필요한 패키지:
- obs-websocket-py
- requests

설정 파일(abc_config.json)이 프로그램과 같은 경로에 있어야 합니다.
"""

import time
import requests
import json
from obswebsocket import obsws, requests as obsrequests
import threading
import logging

# 버전 정보
VERSION = "1.0.0"

# 시작 시 버전 표시
print(f"\nauto-obs-srt-bitrate-rtt-alert_kr v{VERSION}")
print("=" * 50 + "\n")

# OBS WebSocket 라이브러리의 불필요한 로그 메시지 비활성화
logging.getLogger('websockets.client').setLevel(logging.ERROR)
logging.getLogger('obswebsocket').setLevel(logging.ERROR)

# 프로그램 로거 설정
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

class BitrateMonitor:
    def __init__(self, config_path):
        """초기화 함수
        
        Args:
            config_path (str): 설정 파일 경로
        """
        self.config = self._load_config(config_path)
        self._validate_config(self.config)
        self.ws = None                    # OBS WebSocket 연결 객체
        self.last_sent_time = 0           # 마지막 경고 시간
        self.ignore_count = 0             # 초기 체크 무시 카운터
        self.warning_active = False       # 경고 활성화 상태
        self.bitrate_none_logged = False  # 비트레이트 없음 로그 상태
        self.server_connected = False     # 서버 연결 상태
        self.server_retry_count = 0       # 서버 재연결 시도 횟수
        self.obs_retry_count = 0          # OBS 재연결 시도 횟수
        self.source_id = None             # OBS 소스 ID 캐시
        self.is_connected = False         # OBS 연결 상태
        self.connect_to_obs()             # 초기 OBS 연결

    def _validate_config(self, config):
        """설정값 유효성 검사
        
        Args:
            config (dict): 설정값 딕셔너리
            
        Raises:
            ValueError: 설정값이 유효하지 않을 경우
        """
        validation_rules = {
            "BITRATE_THRESHOLD": lambda x: isinstance(x, (int, float)) and x > 0,
            "SOURCE_DISPLAY_TIME": lambda x: isinstance(x, (int, float)) and x > 1,
            "COOLDOWN_SECONDS": lambda x: isinstance(x, (int, float)) and x > config["SOURCE_DISPLAY_TIME"],
            "OBS_PORT": lambda x: isinstance(x, int) and x > 0,
            "RTT_THRESHOLD": lambda x: isinstance(x, (int, float)) and x > 1  # RTT 검증 규칙 추가
        }
        
        string_fields = ["STATS_URL", "PUBLISHER", "OBS_HOST", "OBS_PASSWORD", "SOURCE_NAME", "SCENE_NAME"]
        
        # 숫자 필드 검증
        for field, validator in validation_rules.items():
            if not validator(config[field]):
                raise ValueError(f"{field} 설정값이 올바르지 않습니다")
        
        # 문자열 필드 검증
        if not all(isinstance(config.get(field), str) and config.get(field) for field in string_fields):
            raise ValueError("필수 문자열 설정값이 누락되었거나 올바르지 않습니다")

    def get_retry_delay(self, retry_count):
        """재연결 대기 시간 계산 (지수 백오프)
        
        Args:
            retry_count (int): 재시도 횟수
            
        Returns:
            int: 대기 시간(초)
        """
        # 2초부터 시작하여 최대 32초까지 지수적으로 증가
        delay = min(2 * (2 ** retry_count), 32)
        return delay

    def connect_to_obs(self):
        """
        OBS WebSocket 연결 수행
        
        반환값:
            bool: 연결 성공 여부
        """
        try:
            if self.ws:  # 기존 연결이 있다면 연결 해제
                self.ws.disconnect()
            
            # 새로운 WebSocket 연결 생성
            self.ws = obsws(self.config["OBS_HOST"], self.config["OBS_PORT"], self.config["OBS_PASSWORD"])
            self.ws.connect()
            self.is_connected = True
            logger.info("OBS WebSocket 연결 성공")
            self.obs_retry_count = 0  # 연결 성공시 재시도 카운터 초기화
            self.source_id = None  # 소스 ID 캐시 초기화
            return True
        except Exception as e:
            if self.is_connected:
                logger.error("OBS WebSocket 연결이 끊어졌습니다")
                self.is_connected = False
            delay = self.get_retry_delay(self.obs_retry_count)
            logger.error(f"OBS WebSocket 연결 실패: {e}. {delay}초 후 재시도...")
            self.obs_retry_count += 1
            return False

    def ensure_obs_connection(self):
        # OBS WebSocket 연결 상태를 확인하고 필요시 재연결
        if not self.ws or not self.ws.ws.connected:
            if self.is_connected:  # 이전에 연결되어 있었다면
                logger.error("OBS WebSocket 연결이 끊어졌습니다")
                self.is_connected = False
            return self.connect_to_obs()
        return True

    def _load_config(self, config_path):
        # 설정 파일을 로드하고 필수 필드 확인
        try:
            with open(config_path, "r") as config_file:
                config = json.load(config_file)
                required_fields = ["STATS_URL", "PUBLISHER", "OBS_HOST", 
                                 "OBS_PORT", "OBS_PASSWORD", "SOURCE_NAME",
                                 "SCENE_NAME", "BITRATE_THRESHOLD", "RTT_THRESHOLD",
                                 "COOLDOWN_SECONDS", "SOURCE_DISPLAY_TIME"]
                if not all(field in config for field in required_fields):
                    raise ValueError("필수 설정 필드가 누락되었습니다")
                return config
        except Exception as e:
            raise RuntimeError(f"설정 파일 로드 실패: {e}")

    def _fetch_bitrate(self):
        """SRT 서버에서 비트레이트와 RTT 정보를 가져옴
        
        Returns:
            tuple: (비트레이트, RTT, 서버연결상태)
        """
        try:
            if not hasattr(self, 'session'):
                self.session = requests.Session()
            
            response = self.session.get(self.config["STATS_URL"], timeout=1)
            response.raise_for_status()
            
            if not self.server_connected:
                logger.info("SRT 서버 연결 성공")
                self.server_connected = True
                self.server_retry_count = 0
            
            data = response.json()
            publishers = data.get("publishers", {})
            publisher_data = publishers.get(self.config["PUBLISHER"], {})
            bitrate = publisher_data.get("bitrate")
            rtt = publisher_data.get("rtt", 0)  # RTT 값 추가
            
            if bitrate is None and not self.bitrate_none_logged:
                logger.info("스트림 없음. 스트림이 시작될 때까지 대기 중...")
                self.bitrate_none_logged = True
            elif bitrate is not None:
                self.bitrate_none_logged = False
            
            return bitrate, rtt, True

        except requests.exceptions.RequestException as e:
            delay = self.get_retry_delay(self.server_retry_count)
            logger.error(f"SRT 서버 연결 안됨: {e}. {delay}초 후 재시도...")
            self.server_connected = False
            self.server_retry_count += 1
            self.bitrate_none_logged = False
            return None, None, False

    def _toggle_warning(self, visible):
        """OBS 경고 소스 표시/숨김 처리
        
        Args:
            visible (bool): True=표시, False=숨김
        """
        try:
            self.ws.call(obsrequests.SetSceneItemEnabled(
                sceneName=self.config["SCENE_NAME"],
                sceneItemId=self._get_source_id(),
                sceneItemEnabled=visible
            ))
        except Exception as e:
            logger.error(f"경고 표시/숨김 오류: {e}")

    def _get_source_id(self):
        """OBS 소스 ID 조회 (캐시 사용)
        
        Returns:
            int: 소스 ID
            
        Raises:
            ValueError: 소스를 찾을 수 없을 경우
        """
        if self.source_id is None:
            try:
                scene_items = self.ws.call(obsrequests.GetSceneItemList(sceneName=self.config["SCENE_NAME"]))
                for item in scene_items.datain["sceneItems"]:
                    if item["sourceName"] == self.config["SOURCE_NAME"]:
                        self.source_id = item["sceneItemId"]
                        return self.source_id
                raise ValueError(f"소스 '{self.config['SOURCE_NAME']}'를 장면에서 찾을 수 없습니다")
            except Exception as e:
                logger.error(f"소스 ID 가져오기 오류: {e}")
                raise
        return self.source_id

    def _show_warning_for_duration(self):
        """경고 표시 및 타이머 관리 최적화"""
        if self.warning_active:
            return
        
        self.warning_active = True
        current_bitrate = self._fetch_bitrate()[0]
        logger.warning(f"낮은 비트레이트 경고 - {current_bitrate} kbps (재알림 대기: {self.config['COOLDOWN_SECONDS']}초)")
        
        try:
            self._toggle_warning(True)
            
            # 타이머 객체 재사용
            if hasattr(self, 'warning_timer') and self.warning_timer.is_alive():
                self.warning_timer.cancel()
            
            self.warning_timer = threading.Timer(
                self.config["SOURCE_DISPLAY_TIME"],
                self._hide_warning
            )
            self.warning_timer.daemon = True
            self.warning_timer.start()
            
        except Exception as e:
            logger.error(f"경고 표시 중 오류 발생: {e}")
            self.warning_active = False

    def _hide_warning(self):
        """경고 숨김 처리를 별도 메서드로 분리"""
        try:
            self._toggle_warning(False)
            self.warning_active = False
            logger.info(f"낮은 비트레이트 경고 종료 [{self.config['SOURCE_NAME']} 숨김]")
        except Exception as e:
            logger.error(f"경고 숨김 중 오류 발생: {e}")

    def _handle_low_bitrate(self, bitrate, rtt):
        """비트레이트 또는 RTT 문제 발생시 처리
        
        Args:
            bitrate (float): 현재 비트레이트
            rtt (float): 현재 RTT
        """
        current_time = time.time()
        if current_time - self.last_sent_time >= self.config["COOLDOWN_SECONDS"] and not self.warning_active:
            self.warning_active = True
            
            # 경고 메시지 생성
            warning_reason = []
            if bitrate < self.config["BITRATE_THRESHOLD"]:
                warning_reason.append(f"낮은 비트레이트: {bitrate} kbps")
            if rtt > self.config["RTT_THRESHOLD"]:
                warning_reason.append(f"높은 RTT: {rtt} ms")
            
            warning_msg = " / ".join(warning_reason)
            logger.warning(f"스트림 품질 경고 - {warning_msg} (재알림 대기: {self.config['COOLDOWN_SECONDS']}초) [{self.config['SOURCE_NAME']} 표시됨]")
            
            self._toggle_warning(True)
            
            def hide_warning():
                time.sleep(self.config["SOURCE_DISPLAY_TIME"])
                self._toggle_warning(False)
                self.warning_active = False
                logger.info(f"스트림 품질 경고 종료 [{self.config['SOURCE_NAME']} 숨김]")
            
            threading.Thread(target=hide_warning, daemon=True).start()
            self.last_sent_time = current_time

    def run(self):
        """메인 모니터링 루프
        - 2초 간격으로 비트레이트와 RTT를 체크
        - 문제 발생시 경고 표시
        - 연결 끊김시 자동 재연결
        """
        initial_wait_start = None
        
        while True:
            if not self.ensure_obs_connection():
                delay = self.get_retry_delay(self.obs_retry_count - 1)
                time.sleep(delay)
                continue

            bitrate, rtt, server_connected = self._fetch_bitrate()
            
            if not server_connected:
                delay = self.get_retry_delay(self.server_retry_count - 1)
                time.sleep(delay)
                continue
            
            if self.ignore_count == 0 and bitrate is not None:
                self._handle_initial_period()
                initial_wait_start = time.time()
            elif initial_wait_start is not None:
                elapsed_time = time.time() - initial_wait_start
                if elapsed_time >= 15:
                    initial_wait_start = None
                continue
            
            # 비트레이트나 RTT가 임계값을 벗어날 때 경고 처리
            elif bitrate is not None and (bitrate < self.config["BITRATE_THRESHOLD"] or rtt > self.config["RTT_THRESHOLD"]):
                self._handle_low_bitrate(bitrate, rtt)
            
            time.sleep(2)

    def _handle_initial_period(self):
        """초기 안정화 기간 처리
        - 스트림 시작 후 15초 동안은 체크 건너뜀
        """
        logger.info("스트림 감지됨. 처음 15초 동안은 비트레이트 체크를 건너뜁니다...")
        self.ignore_count = 1

if __name__ == "__main__":
    try:
        monitor = BitrateMonitor("abc_config.json")
        monitor.run()
    except Exception as e:
        logger.error(f"에러 발생: {e}")
        logger.error(f"프로그램이 10초 후 종료됩니다.")
        time.sleep(10)
        raise
