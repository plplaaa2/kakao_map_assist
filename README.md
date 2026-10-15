# KakaoMap

Home Assistant에서 카카오맵 장소와 경로를 검색하는 커스텀 통합입니다. 버전은 `0.1.0`입니다.
REST API 키를 설정하고 `kakaomap.search_places`로 장소 정보,
`kakaomap.search_nearby`로 주변 장소, `kakaomap.get_route`로 이동 경로를 조회합니다. 센서는 생성하지 않으며,
HA LLM API를 지원하는 대화 에이전트에서 `KakaoMap` 도구 제공자를 선택해 사용할 수 있습니다.
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

## API 인증 실패 알림

장소 검색이나 경로 조회 중 API가 인증을 거부하면 HA 알림 패널에
**KakaoMap API 키 확인 필요** 알림을 표시하고 재인증 절차를 시작합니다.
Assist 도구를 통한 조회에도 적용됩니다. 같은 연결의 반복 오류는 하나의 알림으로 유지합니다.

설정 → 기기 및 서비스 → KakaoMap에서 재인증 또는 재설정으로 유효한 키를
등록하면 알림이 자동으로 해제됩니다. 새 키 검증이 실패하면 알림을 유지합니다.
알림에는 API 키나 API 응답 원문을 포함하지 않으며, 인증 실패만으로 키 만료를
단정하지 않습니다. 연결 오류·호출 한도·권한 오류는 인증 실패 알림의 대상이 아닙니다.
키를 주기적으로 검사하지 않으므로 실제 조회에서 인증 실패가 확인될 때 알림을 표시합니다.

## Assist 도구 제공자 연결

1. 업데이트한 `custom_components/kakaomap` 파일을 HA에 반영하고 HA를 재시작합니다.
2. KakaoMap 통합이 REST API 키로 설정되어 정상적으로 로드되었는지 확인합니다.
3. 사용하는 LLM 대화 에이전트의 설정에서 도구 제공자 또는 Home Assistant API 선택 항목을 엽니다.
4. 목록에서 **KakaoMap**을 선택하고 저장합니다. 항목 이름과 위치는 에이전트별로 다를 수 있습니다.
5. Assist에서 해당 대화 에이전트를 사용하는 어시스턴트를 선택하고 질문합니다.

HA LLM API를 지원하는 에이전트가 필요합니다. 기본 문장 인식 에이전트만으로는
이 도구를 호출할 수 없습니다. 집 제어도 함께 사용하려면 에이전트가 여러 API 선택을
지원하는 경우 기존 Assist API와 KakaoMap을 함께 선택합니다.
KakaoMap 도구는 다른 API에 자동으로 추가하지 않으며, 제공자를 선택해야 사용할 수 있습니다.

| 도구 | 역할 |
| --- | --- |
| `kakaomap__search_places` | 이름·주소로 장소 후보와 좌표 조회 |
| `kakaomap__search_nearby` | 중심 좌표 주변의 키워드·카테고리 검색, 거리순 반환 |
| `kakaomap__get_route` | 출발·도착 좌표로 경로 조회, 대중교통 기본 |
| `kakaomap__get_home_location` | HA에 설정된 집 좌표 조회 |

"서울역 주소 알려줘", "집에서 서울역까지 얼마나 걸려?", "거기까지 걸어서 가면?"
처럼 질문할 수 있습니다. 사용자는 좌표를 입력하지 않아도 됩니다. 집 좌표는
집 위치 도구가 호출될 때 제공되며 휴대전화의 실시간 위치를 조회하지 않습니다.

제공자가 목록에 없으면 HA 재시작, KakaoMap 통합 로드 여부, 에이전트의 HA LLM API
지원 여부를 확인하세요. 내부 제공자 ID는 `kakaomap-<config entry ID>`이며
HA의 등록된 LLM API 목록에 표시 이름 `KakaoMap`으로 등록됩니다.
통합이 해제되면 제공자도 해제되고, 설정 재로드 시 다시 등록됩니다.

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

대화 에이전트에서 사용하려면 위의 Assist 연결 절차에 따라 KakaoMap 제공자를 선택합니다.

## 주변 장소 검색 액션

`kakaomap.search_nearby`는 중심 좌표의 반경 안에서 가까운 순으로 장소를 검색합니다.
`latitude`, `longitude`는 필수이며 `query`(키워드) 또는 `category`(카테고리 코드)
중 정확히 하나를 입력합니다. 반경 `radius`는 1~20000m(기본 1000m),
결과 수 `limit`은 1~15개(기본 5개)입니다. 카카오 공식 키워드·카테고리 API를 사용합니다.

```yaml
action: kakaomap.search_nearby
data:
  latitude: 37.5665
  longitude: 126.9780
  category: PM9
  radius: 1000
  limit: 5
response_variable: nearby_result
```

업체명 검색은 `category` 대신 `query: 스타벅스`를 지정합니다.
카테고리는 액션 화면에서 한글 이름으로 선택할 수 있습니다.

| 코드 | 업종 | 코드 | 업종 |
| --- | --- | --- | --- |
| MT1 | 대형마트 | CS2 | 편의점 |
| PS3 | 어린이집·유치원 | SC4 | 학교 |
| AC5 | 학원 | PK6 | 주차장 |
| OL7 | 주유소·충전소 | SW8 | 지하철역 |
| BK9 | 은행 | CT1 | 문화시설 |
| AG2 | 중개업소 | PO3 | 공공기관 |
| AT4 | 관광명소 | AD5 | 숙박 |
| FD6 | 음식점 | CE7 | 카페 |
| HP8 | 병원 | PM9 | 약국 |

응답에는 `query`, `category`, 중심 좌표 `center`, 반경 `radius_m`,
`count`, `total_count`, `is_end`, `places`가 있습니다. 장소 항목은 기존 검색과
동일하며 숫자형 `distance_m`이 추가됩니다. 이 값은 중심 좌표 기준 거리이며
도보 이동 거리나 이동 시간이 아닙니다. 첫 페이지에서 최대 `limit`개만 반환합니다.
검색 결과가 없으면 빈 목록을 반환하며 반경을 자동으로 넓히지 않습니다.
인증·권한·한도·연결 오류는 기존 장소 검색과 동일하게 처리합니다.

Assist에서는 "집 근처 약국 찾아줘"라고 하면 집 위치 도구로 중심 좌표를 얻고,
"서울역 주변 카페"라면 장소 검색으로 서울역을 확인한 뒤 주변 검색을 수행하도록
지침을 제공합니다. 중심 장소가 모호하면 후보를 확인합니다. 현재 휴대전화 위치는
자동으로 조회하지 않으며, 위치를 모르면 사용자에게 기준 위치를 확인합니다.
반경을 말하지 않으면 1km를 사용합니다. 실제 도구 선택은 연결한 LLM에 따라 다릅니다.

## 경로 조회 액션

`kakaomap.get_route`는 출발·도착 위도/경도 네 항목을 필수로 받습니다.
좌표는 WGS84 기준이며, 장소 검색 결과의 `latitude`와 `longitude`를 사용할 수 있습니다.
이동 수단 `mode`는 `public_transport`(기본값, 대중교통), `walk`(도보),
`bicycle`(자전거)입니다. 출발·도착 이름은 선택 입력이며 각각 `출발`, `도착`이 기본값입니다.

**이동 수단을 지정하지 않으면 대중교통으로 조회합니다.** 아래 예시에서도
`mode`를 생략해 기본값을 사용합니다. 도보는 `mode: walk`, 자전거는
`mode: bicycle`을 명시했을 때 조회합니다.

```yaml
action: kakaomap.get_route
data:
  start_latitude: 37.3947766
  start_longitude: 127.1111967
  end_latitude: 37.4199324
  end_longitude: 127.1262904
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
"집에서"라는 요청에는 에이전트가 집 위치 도구로 HA 집 좌표를 조회합니다.
"현재 위치에서"라는 요청은 출발 위치를 확인해야 합니다. 경로 액션 자체는 집이나
휴대전화 위치를 자동으로 선택하지 않습니다.

## 대화 에이전트에서의 사용 규칙

KakaoMap 제공자는 다음 지침을 대화 에이전트에 전달합니다. 액션의 기본값도
대중교통입니다. 자연어 해석과 도구 선택은 연결한 LLM 에이전트가 수행하므로,
실제 대화에서는 사용하는 에이전트와 모델의 동작을 확인하세요.

- 이동 수단을 말하지 않으면 대중교통으로 조회합니다. 매번 이동 수단을 묻지 않습니다.
- 사용자가 "걸어서", "도보로"라고 요청한 경우에만 도보로 조회합니다.
- 사용자가 "자전거로"라고 요청한 경우에만 자전거로 조회합니다.
- 대중교통 결과가 없더라도 도보·자전거로 자동 전환하지 않습니다.
- 목적지 후보가 여러 개면 장소를 확인한 뒤 경로를 조회합니다.

| 요청 예시 | 사용할 이동 수단 |
| --- | --- |
| "집에서 서울역까지 얼마나 걸려?" | 대중교통 `public_transport` |
| "거기까지 걸어서 가면?" | 도보 `walk` |
| "자전거로 가는 길 알려줘" | 자전거 `bicycle` |

대화에서는 소요 시간, 대중교통 환승과 요금, 주요 이동 안내를 요약하도록
지침을 전달합니다. 장소·길찾기 링크는 대화 답변에 붙이거나 읽지 않습니다.
자동화에서 사용할 수 있도록 액션과 도구의 반환 데이터에는 링크를 유지합니다.

## 기본 구조

실행에 필요한 파일은 `custom_components/kakaomap/`에 배치합니다.
`manifest.json`은 Home Assistant 메타데이터이며, 루트의 `hacs.json`은
HACS 표시 이름과 README 렌더링을 설정합니다. 전체 구조는 `tree.md`를 참고하세요.

## 구현 전에 결정할 사항

- GitHub 저장소 주소와 관리자 계정
- 라이선스와 브랜드 이미지
- 사용할 LLM 대화 에이전트와 실제 대화 동작 검증

`manifest.json`의 `example.com` 주소는 교체가 필요한 자리표시자입니다.
`codeowners`에는 실제 GitHub 관리자를 등록해야 합니다.
사용자 지정 버전 `0.1.0`과 검증 기준에 맞춘 HA 최소 버전 `2026.10.1`을 설정했습니다.
실제 GitHub 저장소 정보가 없으므로 현재 HACS 공개 배포용 메타데이터는 미완성입니다.

## 이후 확장할 파일

`config_flow.py`와 번역 파일은 API 키 설정을, `api.py`는 검색과 경로 HTTP 요청을 처리합니다.
`routes.py`는 이동 수단별 API 응답을 공통 경로 요약으로 변환합니다.
`__init__.py`와 `services.yaml`은 응답 액션을 제공합니다.
`llm.py`는 선택 가능한 Assist 제공자, 도구 및 대화 지침을 제공합니다.
`notifications.py`는 인증 실패 알림과 키 교체 성공 시 알림 해제를 처리합니다.
`tests/`는 HTTP 응답 처리, 실제 HA 액션 호출, 설정과 키 교체를 검증합니다.

## 개발 검증

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
git diff --check
```

테스트는 가짜 인증 정보와 로컬 HTTP 서버를 사용하며 실제 카카오 API를 호출하지 않습니다.
HA의 실제 LLM API 목록 조회, 도구 호출, 등록 해제 및 재등록을 자동 테스트합니다.
실제 키를 사용한 검색·경로 조회, HA 화면에서의 제공자 선택 및 LLM 모델을 통한
대화는 별도 검증이 필요합니다.

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
- [Home Assistant LLM 도구 및 API 등록](https://developers.home-assistant.io/docs/core/llm/)
- [HACS 통합 요구사항](https://www.hacs.dev/docs/publish/integration/)
- [HACS 공통 요구사항 및 hacs.json](https://hacs.dev/docs/publish/start/)
- [Home Assistant 통합 파일 구조](https://developers.home-assistant.io/docs/creating_integration_file_structure/)
- [Home Assistant manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/)
