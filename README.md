# KakaoMap

Home Assistant에서 카카오맵 장소와 경로를 검색하는 커스텀 통합입니다. 버전은 `0.1.0`입니다.
REST API 키를 설정하고 `kakaomap.search_places`로 장소 정보,
`kakaomap.get_route`로 이동 경로를 조회합니다. 센서는 생성하지 않으며,
대화 에이전트의 도구 연결은 별도 작업입니다.
Windows에서 Home Assistant `2026.10.1`을 기준으로 개발 및 자동 테스트했습니다.

## 설정

1. 카카오디벨로퍼스에서 앱을 만들고 [카카오맵] → [사용 설정]을 ON으로 설정합니다.
2. 해당 앱의 REST API 키를 준비합니다.
3. `custom_components/kakaomap` 폴더를 HA 설정 폴더의 `custom_components`에 복사하고 재시작합니다.
4. 설정 → 기기 및 서비스 → 통합 구성요소 추가에서 `KakaoMap`을 선택합니다.
5. REST API 키를 입력합니다. 유효성 확인을 위해 검색 요청 1회를 수행합니다.

통합은 연결 하나만 지원합니다. 통합의 재설정 메뉴에서 키를 교체할 수 있습니다.
검색 중 인증에 실패하면 재인증 절차를 시작합니다. API 키는 HA 구성 항목에 저장되며
로그와 검색 결과에는 포함되지 않습니다. HA 백업에는 인증 정보가 포함될 수 있습니다.

## 장소 검색 액션

개발자 도구 → 액션에서 `kakaomap.search_places`를 호출하면 응답을 확인할 수 있습니다.
`name` 또는 `address` 중 하나 이상을 입력하세요. `limit`은 1~15이며 기본값은 5입니다.

```yaml
action: kakaomap.search_places
data:
  name: 스타벅스
  address: 서울 강남구
  limit: 5
response_variable: search_result
```

스크립트와 자동화에서는 `search_result.places`로 장소 목록을 사용할 수 있습니다.
주소와 이름은 하나의 키워드로 합쳐 검색하므로 여러 후보가 반환될 수 있습니다.
주소만 입력해도 장소 검색을 수행하며, 주소 자체의 좌표 변환 기능은 아닙니다.
최신 API의 검색 범위 요구사항에 맞춰 한국 주변 영역(경도 124~132, 위도 32~40)을
사용합니다. HA의 집 위치로 검색을 제한하지 않습니다.

응답에는 `query`, 실제 반환 수 `count`, 전체 검색 수 `total_count`, 현재 페이지의
마지막 여부 `is_end`, 장소 목록 `places`가 있습니다. 첫 페이지에서 최대 `limit`개만
반환합니다. 각 장소에는 `id`, `place_name`, `address_name`, `road_address_name`,
`phone`, `category_name`, `place_url`, 숫자형 `latitude`, `longitude`가 있습니다.
제공되지 않는 전화번호나 도로명 주소는 빈 문자열일 수 있습니다.
검색 결과가 없으면 `places: []`를 반환합니다. 인증, 권한, 호출 한도, 연결 및
응답 오류는 HA 액션 오류로 표시합니다. 평점, 리뷰, 영업시간은 제공하지 않습니다.

대화 에이전트가 자동으로 이 액션을 사용할 수 있는 것은 아닙니다.
사용할 에이전트에 맞는 도구 등록 또는 LLM API 연결을 추가해야 합니다.

## 경로 조회 액션

`kakaomap.get_route`는 출발·도착 위도/경도 네 항목을 필수로 받습니다.
좌표는 WGS84 기준이며, 장소 검색 결과의 `latitude`와 `longitude`를 사용할 수 있습니다.
이동 수단 `mode`는 `public_transport`(기본값, 대중교통), `walk`(도보),
`bicycle`(자전거)입니다. 출발·도착 이름은 선택 입력이며 각각 `출발`, `도착`이 기본값입니다.

```yaml
action: kakaomap.get_route
data:
  start_latitude: 37.3947766
  start_longitude: 127.1111967
  end_latitude: 37.4199324
  end_longitude: 127.1262904
  mode: public_transport
  start_name: 출발역
  end_name: 도착역
response_variable: route_result
```

응답은 `mode`, 경로 수 `count`, 길찾기 링크 `route_url`, 경로 목록 `routes`입니다.
각 경로에는 `distance_m`(미터), `duration_s`(초), `duration_minutes`(분),
`route_url`, 이동 유형 `mode`, 구간별 안내 `steps`가 있습니다.
대중교통 경로에는 `transfers`(환승 횟수), `fare`(원 단위 요금 정보)가 포함됩니다.
`fare`는 API가 제공한 `value`, `min`, `max`만 포함하며 제공되지 않으면 `null`입니다.
도보·자전거의 요금과 환승 횟수는 `null`입니다.
대중교통 구간에는 정류장 이름 `stops`와 버스·지하철 이름/유형 `vehicles`도 포함됩니다.
경로 지도용 좌표 배열은 응답 크기를 줄이기 위해 제외합니다.

경로가 없으면 `routes: []`를 반환합니다. 동일 출발·도착지, 주변 도로/정류장을
찾을 수 없는 경우, 너무 먼 경로 및 탐색 실패는 액션 오류로 표시합니다.
소요 시간은 경로 조회 결과이며 실시간 버스 도착 시간 정보가 아닙니다.
자동차 경로, 경유지 지정 및 경로 탐색 옵션은 이번 액션에 포함하지 않았습니다.

대화 도구에서는 장소 검색 → 후보 확인 → 좌표 선택 → 경로 조회 순서로 호출하면 됩니다.
"집에서"라는 요청에는 도구 연결 단계에서 HA 집 좌표를 넣고, "현재 위치에서"라는
요청에는 사용자가 선택한 위치 출처의 좌표를 넣어야 합니다. 이 액션은 집이나
휴대전화 위치를 자동으로 선택하지 않습니다.

## 기본 구조

실행에 필요한 파일은 `custom_components/kakaomap/`에 배치합니다.
`manifest.json`은 Home Assistant 메타데이터이며, 루트의 `hacs.json`은
HACS 표시 이름과 README 렌더링을 설정합니다. 전체 구조는 `tree.md`를 참고하세요.

## 구현 전에 결정할 사항

- GitHub 저장소 주소와 관리자 계정
- 라이선스와 브랜드 이미지
- 사용할 대화 에이전트와 검색 도구 연결 방식

`manifest.json`의 `example.com` 주소는 교체가 필요한 자리표시자입니다.
`codeowners`에는 실제 GitHub 관리자를 등록해야 합니다.
사용자 지정 버전 `0.1.0`과 검증 기준에 맞춘 HA 최소 버전 `2026.10.1`을 설정했습니다.
실제 GitHub 저장소 정보가 없으므로 현재 HACS 공개 배포용 메타데이터는 미완성입니다.

## 이후 확장할 파일

`config_flow.py`와 번역 파일은 API 키 설정을, `api.py`는 검색과 경로 HTTP 요청을 처리합니다.
`routes.py`는 이동 수단별 API 응답을 공통 경로 요약으로 변환합니다.
`__init__.py`와 `services.yaml`은 응답 액션을 제공합니다.
`tests/`는 HTTP 응답 처리, 실제 HA 액션 호출, 설정과 키 교체를 검증합니다.

## 개발 검증

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
git diff --check
```

테스트는 가짜 인증 정보와 로컬 HTTP 서버를 사용하며 실제 카카오 API를 호출하지 않습니다.
실제 키를 사용한 검색·경로 조회, HA 화면 설정 및 대화 에이전트 연동은 별도 검증이 필요합니다.

## 개발 관리

로직 구현 전 변경 파일과 단계별 계획을 승인받습니다.
소스와 문서는 UTF-8 BOM 없이 유지하고, 비밀 값은 소스나 로그에 기록하지 않습니다.
애플리케이션 로그의 기본 수준은 INFO로 하고 필요에 따라 WARN, ERROR, DEBUG를 구분합니다.
변경 이력은 `changelog.jsonl`, 주의사항은 `caution.jsonl`에서 관리합니다.

사용자 승인에 따라 이번 작업은 원격 push 대신 로컬 `dev` 커밋으로 백업합니다.
원격 저장소 연결 후 기존 작업 지침에 따라 dev push 절차를 적용합니다.
HACS 배포 전에는 실제 메타데이터, 공개 GitHub 저장소, 설명/토픽,
브랜드 요건 및 HACS/HA 검증 결과를 확인해야 합니다.

## 공식 참고 문서

- [카카오맵 API 소개와 활성화](https://developers.kakao.com/docs/ko/kakaomap/common#rest-api)
- [카카오맵 REST API](https://developers.kakao.com/docs/ko/kakaomap/rest-api)
- [Home Assistant 응답 액션](https://developers.home-assistant.io/docs/dev_101_services/)
- [HACS 통합 요구사항](https://www.hacs.dev/docs/publish/integration/)
- [HACS 공통 요구사항 및 hacs.json](https://hacs.dev/docs/publish/start/)
- [Home Assistant 통합 파일 구조](https://developers.home-assistant.io/docs/creating_integration_file_structure/)
- [Home Assistant manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/)
