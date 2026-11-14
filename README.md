# KakaoMap for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
![버전 v1.0.0](https://img.shields.io/badge/version-v1.0.0-blue.svg?style=for-the-badge)
[![Ko-fi 후원](https://img.shields.io/badge/Ko--fi-Support%20Me-F16061?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/plplaaa2)

Home Assistant에서 카카오맵 장소와 이동 경로를 조회하는 커스텀 통합입니다.
Home Assistant 액션과 호환되는 Assist 대화 에이전트에서 사용할 수 있습니다.

[설치](#설치) · [설정](#설정) · [Assist 연결](#assist-도구-제공자-연결) · [문제 제보](#문제-제보)

## 주요 기능

| 기능 | Home Assistant 액션 |
| --- | --- |
| 이름이나 키워드로 장소 검색 | [`kakaomap.search_places`](#장소-검색-액션) |
| 도로명·지번 주소를 좌표로 조회 | [`kakaomap.geocode_address`](#주소-조회-액션) |
| 주변 장소를 키워드·카테고리로 검색 | [`kakaomap.search_nearby`](#주변-장소-검색-액션) |
| 대중교통·도보·자전거·자동차 경로 조회 | [`kakaomap.get_route`](#경로-조회-액션) |

자동차 경로는 경유지, 대안 경로 비교, 미래 출발 시각을 지원합니다.
Assist에서는 “집에서 서울역까지 얼마나 걸려?”처럼 질문할 수 있습니다.
이 통합은 센서를 생성하지 않습니다.

## 설치

Home Assistant `2026.10.1` 이상이 필요합니다.

### HACS

[![HACS에서 KakaoMap 저장소 열기](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=plplaaa2&repository=kakao_map_assist&category=integration)

위 버튼으로 HACS에서 저장소를 열고, 필요하면 사용자 지정 저장소로 추가합니다.
KakaoMap을 다운로드한 뒤 Home Assistant를 재시작합니다.

### 수동 설치

수동으로 설치하려면 `custom_components/kakaomap` 폴더를 Home Assistant 설정 폴더의
`custom_components/` 아래에 복사한 뒤 Home Assistant를 재시작합니다.

## 설정

1. 카카오디벨로퍼스에서 앱을 만들고 [카카오맵] → [사용 설정]을 ON으로 설정합니다.
2. 해당 앱의 REST API 키를 준비합니다.
3. 설정 → 기기 및 서비스 → 통합 구성요소 추가에서 `KakaoMap`을 선택합니다.
4. REST API 키를 입력합니다. 유효성 확인을 위해 검색 요청 1회를 수행합니다.

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
| `kakaomap__geocode_address` | 도로명·지번 주소로 좌표와 주소 후보 조회 |
| `kakaomap__search_nearby` | 중심 좌표 주변의 키워드·카테고리 검색, 거리순 반환 |
| `kakaomap__get_route` | 출발·도착 좌표로 경로 조회, 대중교통 기본 |
| `kakaomap__get_home_location` | HA에 설정된 집 좌표 조회 |
| `kakaomap__get_current_location` | 로그인 사용자와 연결된 사람의 위치 조회, 재택이면 집 좌표 사용 |

"서울역 주소 알려줘", "집에서 서울역까지 얼마나 걸려?", "거기까지 걸어서 가면?"
처럼 질문할 수 있습니다. 사용자는 좌표를 입력하지 않아도 됩니다. 집 좌표는
집 위치 도구가 호출될 때 제공됩니다. 현재 위치 도구는 로그인 사용자와 연결된
`person`의 HA 최신 상태를 사용하며 휴대전화에 새 GPS 측정을 요청하지 않습니다.

### 대화 사용자의 현재 위치

"근처 약국 찾아줘", "여기서 서울역까지", 출발지를 생략한 "서울역까지 얼마나 걸려?"에는
현재 위치 도구를 먼저 호출하도록 안내합니다. 도구는 대화 요청의 사용자 ID와
`person`의 `user_id`를 내부에서 연결하므로 사용자가 엔티티 이름을 말할 필요는 없습니다.

- 연결된 사람의 상태가 `home`이면 HA에 설정된 집 좌표를 사용합니다.
- 외출 중이면 연결된 사람의 위도·경도를 사용합니다.
- 로그인 정보나 사람 연결이 없거나, 위치가 불명·사용 불가이면 기준 위치를 확인합니다.
- 다른 가족의 위치나 집 좌표로 임의 대체하지 않습니다.
- "집 근처", "집에서"처럼 집을 명시한 요청은 기존 집 위치 도구를 사용합니다.

설정 → 사람에서 대화에 사용하는 사용자 계정과 사람을 연결하고 위치 추적 기기를
설정해야 합니다. 공유 계정으로 접속하면 그 계정에 연결된 사람 기준이며, 실제 발화자를
식별하는 기능은 아닙니다. 로그인 사용자 정보가 전달되지 않는 음성 기기에서는 기준 위치를 묻습니다.
이 도구는 Assist 전용이며 별도 HA 액션을 추가하지 않습니다.

반환 항목은 `name`, `latitude`, `longitude`, `at_home`, `source`(`home` 또는 `person`),
`state_last_updated`입니다. 마지막 항목은 HA 사람 상태 갱신 시각으로 GPS 측정 시각이나
위치의 최신성을 보장하지 않습니다. 위치는 도구 호출 시에만 읽으며 실제 도구 선택은 LLM에 따릅니다.

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
정확한 도로명·지번 주소는 별도 `kakaomap.geocode_address` 액션을 사용하세요.
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

## 주소 조회 액션

`kakaomap.geocode_address`는 카카오 공식 주소 API로 도로명·지번 주소를
조회합니다. 필수 입력 `query` 하나로 두 주소 형식을 모두 지원합니다.
`limit`은 1~15개이며 기본값은 5개입니다. 기존 장소 검색은 키워드 검색을 유지합니다.

```yaml
action: kakaomap.geocode_address
data:
  query: 서울 중구 세종대로 110
  limit: 5
response_variable: address_result
```

응답은 `query`, `count`, `total_count`, `is_end`, 주소 후보 목록 `addresses`입니다.
각 후보에는 `address_name`, 주소 유형 `address_type`, 숫자형 `latitude`·`longitude`,
지번 주소 `jibun_address`, 도로명 주소 `road_address`, 우편번호 `zone_no`가 있습니다.
API에서 제공하지 않는 지번·도로명·우편번호는 `null`입니다. 주소 유형은
`REGION`(지명), `ROAD`(도로명), `REGION_ADDR`(지번 주소), `ROAD_ADDR`(도로명 주소)입니다.
첫 페이지에서 최대 `limit`개를 반환하고 결과가 없으면 `addresses: []`를 반환합니다.
인증 오류 알림·재인증과 권한·한도·연결 오류 처리는 기존 검색과 같습니다.

Assist의 기본값은 장소명·업체명 키워드 검색입니다. "강남구 카페"는 키워드 검색,
"서울 중구 세종대로 110" 또는 "서울 중구 태평로1가 31"은 주소 조회 도구를
선택하도록 안내합니다. 조회 좌표는 주변 검색의 중심이나 경로의 출발·도착지로
사용할 수 있습니다. 후보가 모호하면 확인하고, 결과가 없을 때 다른 장소로 임의 대체하지 않습니다.
주소 조회는 건물·주소 위치 기준이며 동·호수·층 단위 위치를 보장하지 않습니다.
자동화는 명시적으로 액션을 선택하며, 대화 중 도구 선택은 연결한 LLM이 수행합니다.

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
지침을 제공합니다. 중심 장소가 모호하면 후보를 확인합니다. "내 근처"처럼 현재 위치가
필요하면 로그인 사용자의 위치 도구를 사용하고, 조회할 수 없으면 기준 위치를 확인합니다.
반경을 말하지 않으면 1km를 사용합니다. 실제 도구 선택은 연결한 LLM에 따라 다릅니다.

## 경로 조회 액션

`kakaomap.get_route`는 출발·도착 위도/경도 네 항목을 필수로 받습니다.
좌표는 WGS84 기준이며, 장소 검색 결과의 `latitude`와 `longitude`를 사용할 수 있습니다.
이동 수단 `mode`는 `public_transport`(기본값, 대중교통), `walk`(도보),
`bicycle`(자전거), `car`(자동차)입니다. 출발·도착 이름은 선택 입력이며 각각 `출발`, `도착`이 기본값입니다.

**이동 수단을 지정하지 않으면 대중교통으로 조회합니다.** 아래 예시에서도
`mode`를 생략해 기본값을 사용합니다. 도보는 `mode: walk`, 자전거는
`mode: bicycle`, 자동차는 `mode: car`를 명시했을 때 조회합니다.

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

경로가 있으면 응답 상위에 출발 기준 `departure_time`과 HA 설정 시간대 `time_zone`을,
각 경로에 예상 도착 시각 `arrival_time`을 추가합니다. 시각은 시간대 오프셋을 포함한
ISO 8601 형식입니다. 기본은 조회 시작 시각에 출발하며, 자동차 미래 출발 시각을
지정하면 그 시각을 기준으로 합니다. 도착 시각은 해당 API 소요 시간을 더한 예상값이며 확정값이 아닙니다.
경유지에서 주유·쇼핑 등 머무는 시간은 포함하지 않습니다. 경로가 없으면 도착 시각도 제공하지 않습니다.

경로가 없으면 `routes: []`를 반환합니다. 동일 출발·도착지, 주변 도로/정류장을
찾을 수 없는 경우, 너무 먼 경로 및 탐색 실패는 액션 오류로 표시합니다.
소요 시간은 경로 조회 결과이며 실시간 버스 도착 시간 정보가 아닙니다.
자동차 경로 기준·회피 옵션, 경유지와 대안 경로는 아래와 같이 지정할 수 있습니다.

### 자동차 경로

자동차는 카카오모빌리티의 일반 자동차 길찾기 API를 현재 설정된 REST API 키로
호출합니다. 기본 경로 기준은 추천(`priority: RECOMMEND`)이며, 별도 요청이 없으면
회피 조건을 추가하지 않습니다. 대안 경로는 기본적으로 조회하지 않으며,
비교 요청 시 `alternatives: true`로 한 번의 API 호출에서 함께 조회합니다.

```yaml
action: kakaomap.get_route
data:
  start_latitude: 37.3947766
  start_longitude: 127.1111967
  end_latitude: 37.4199324
  end_longitude: 127.1262904
  mode: car
response_variable: car_result
```

| 입력 | 값 | 용도 |
| --- | --- | --- |
| `priority` | `RECOMMEND` | 추천 경로, 기본값 |
| `priority` | `TIME` | 최단 시간 요청 |
| `priority` | `DISTANCE` | 최단 거리 요청 |
| `avoid` | `[toll]` | 유료도로 회피 |
| `avoid` | `[motorway]` | 자동차 전용도로 회피 |
| `avoid` | `[ferries]` | 페리 회피 |
| `avoid` | `[schoolzone]` | 어린이 보호구역 회피 |
| `avoid` | `[uturn]` | 유턴 회피 |

회피 옵션은 목록으로 여러 개 지정할 수 있습니다. 예: `avoid: [toll, ferries]`.
기본값 이외의 경로 기준이나 회피 옵션을 대중교통·도보·자전거에 지정하면 입력 오류입니다.
큰길 우선 옵션은 지원하지 않습니다.

### 자동차 경유지와 대안 경로 비교

자동차의 `waypoints`에 방문 순서대로 최대 5개 좌표를 지정할 수 있습니다.
각 항목은 `latitude`, `longitude`가 필수이며 `name`은 선택 항목입니다.
이름을 생략하면 `경유지 1`처럼 순서대로 이름을 붙입니다. 입력 순서를 유지하며
방문 순서를 자동 최적화하지 않습니다. 일반 API의 경유지 포함 총 경로 거리는
1,500km 미만이어야 하며 실제 탐색 가능 여부는 API가 판정합니다.

```yaml
action: kakaomap.get_route
data:
  start_latitude: 37.3947766
  start_longitude: 127.1111967
  end_latitude: 37.4199324
  end_longitude: 127.1262904
  mode: car
  waypoints:
    - latitude: 37.4
      longitude: 127.12
      name: 경유 장소
  alternatives: true
response_variable: compared_routes
```

`alternatives: true`는 같은 출발·경유·도착지, 경로 기준과 회피 조건에서 API가
제공하는 다른 후보들을 함께 반환합니다. 추천·최단 시간·무료 경로를 각각 호출해
비교하는 기능은 아닙니다. 후보가 하나뿐이면 한 개만 반환합니다.
상위 응답의 `waypoints`는 적용한 경유지, `alternatives_requested`는 대안 요청 여부입니다.

자동차의 각 후보에는 원본 순서 번호 `route_index`(1부터 시작), 첫 후보 여부 `is_primary`,
시간·거리·통행료·도착 예상 시각이 있습니다. 첫 후보를 유지하며 가장 빠른 후보로
임의 재정렬하지 않습니다. 비교를 요청한 경우 `difference_from_primary`의 `duration_s`,
`distance_m`, `toll_fare`는 첫 후보 대비 차이이며 음수는 더 적음을 뜻합니다.
API가 실패 코드로 반환한 추가 후보는 제외하고 `skipped_alternatives`에 개수를 표시합니다.
첫 경로의 탐색 실패나 잘못된 응답은 기존처럼 액션 오류로 처리합니다.

Assist에서는 "주유소 들렀다가 집까지 차로", "다른 경로도 비교해줘" 같은 요청에만
경유지·대안 옵션을 적용합니다. 경유 장소는 먼저 검색하고 모호하면 사용자에게 확인합니다.
경유지와 대안 옵션은 자동차 전용이며 다른 이동 수단으로 요청하면 오류입니다.

### 자동차 미래 출발 시각

`departure_time`을 지정하면 일반 자동차 API 대신 미래 운행 정보 길찾기 API를
같은 REST API 키로 호출합니다. 생략하면 기존처럼 지금 출발 기준으로 조회합니다.
입력은 UTC 오프셋이 있는 ISO 8601 문자열이며 분 단위로 지정합니다.
예: `2026-10-16T08:00:00+09:00`. 초·소수 초는 0이어야 하며 과거·현재 시각,
시간대 없는 시각, 잘못된 날짜는 API 호출 전에 차단합니다. 예시 날짜는 실제 미래 날짜로 바꿔 사용하세요.

```yaml
action: kakaomap.get_route
data:
  start_latitude: 37.3947766
  start_longitude: 127.1111967
  end_latitude: 37.4199324
  end_longitude: 127.1262904
  mode: car
  departure_time: '2026-10-16T08:00:00+09:00'
response_variable: future_route
```

입력 오프셋을 해석해 동일한 시점을 한국 시간(`Asia/Seoul`)의 API 형식
`YYYYMMDDHHMM`으로 변환합니다. 응답의 `departure_time`과 각 `arrival_time`은
HA 설정 시간대로 표시합니다. 자동차 응답의 `is_future`는 미래 조회 여부,
`requested_at`은 실제 조회 시작 시각이며 출발 시각과 구분합니다.
도착 예상은 미래 출발 시각에 예측 소요 시간을 더한 값이고, 경유지 체류 시간은 제외합니다.

추천·최단 시간·최단 거리, 회피, 경유지, 대안 비교를 미래 조회와 함께 사용할 수 있습니다.
대중교통·도보·자전거의 미래 출발 지정이나 도착 희망 시각으로 출발 시간을 역산하는 기능은
지원하지 않습니다. API의 탐색 가능 기간·경로 제한은 실제 API 응답에 따릅니다.
미래 조회 실패 시 현재 시각 경로로 자동 대체하지 않습니다.

Assist에는 요청 시점의 HA 현재 시각을 전달해 "내일 오전 8시에 차로" 같은 표현을
해석하도록 안내합니다. 날짜·오전/오후가 모호하면 확인하고, 명시한 미래 출발 요청에만
`departure_time`을 사용합니다. 시각을 말하지 않으면 기존 기본값을 유지합니다.

자동차도 기존 `routes` 목록과 시간·거리·`steps` 안내 형식을 사용합니다.
환승 `transfers`와 대중교통 요금 `fare`는 `null`이며, 통행료는 각 경로의
`toll_fare`(원)로 따로 반환합니다. 택시 예상요금과 연료비는 제공하지 않습니다.
상위 응답의 `priority`·`avoid`는 요청 조건, 각 경로의 `priority`는 API 응답의 기준입니다.
유료도로 회피를 요청해도 통행료 0원을 임의로 보장하지 않고 실제 `toll_fare`를 안내합니다.
자동차 탐색 실패는 액션 오류이며 대중교통으로 자동 전환하지 않습니다.

자동차 `route_url`은 출발·경유·도착지를 순서대로 지정한 카카오맵 링크입니다. 출발 시각·경로 기준·회피 옵션이나
API에서 계산된 특정 경로까지 보존하지 않으므로 링크에서 다시 조회한 결과는 다를 수 있습니다.
실제 호출 가능 여부와 무료 쿼터·추가 사용 조건은 사용하는 앱 설정 및 공식 안내를 확인하세요.

대화 도구에서는 장소 검색 → 후보 확인 → 좌표 선택 → 경로 조회 순서로 호출하면 됩니다.
"집에서"라는 요청에는 에이전트가 집 위치 도구로 HA 집 좌표를 조회합니다.
"현재 위치에서" 또는 출발지를 생략한 대화 요청은 로그인 사용자의 위치 도구를 먼저
사용합니다. 위치를 확인할 수 없으면 출발지를 묻습니다. 경로 액션 자체는 기존처럼
명시적인 출발·도착 좌표를 받으며 집이나 사람 위치를 자동으로 선택하지 않습니다.

## 대화 에이전트에서의 사용 규칙

KakaoMap 제공자는 다음 지침을 대화 에이전트에 전달합니다. 액션의 기본값도
대중교통입니다. 자연어 해석과 도구 선택은 연결한 LLM 에이전트가 수행하므로,
실제 대화에서는 사용하는 에이전트와 모델의 동작을 확인하세요.
공통 지침은 검색·위치·경로·답변 규칙으로 묶고 입력 항목 설명은 각 도구에 모아 중복을 줄였습니다.

- 이동 수단을 말하지 않으면 대중교통으로 조회합니다. 매번 이동 수단을 묻지 않습니다.
- 사용자가 "걸어서", "도보로"라고 요청한 경우에만 도보로 조회합니다.
- 사용자가 "자전거로"라고 요청한 경우에만 자전거로 조회합니다.
- 사용자가 "차로", "자동차로"라고 요청한 경우에만 자동차로 조회합니다.
- 자동차는 추천 경로가 기본이며, 최단 시간·최단 거리·회피 옵션은 요청할 때만 적용합니다.
- 자동차 경유지·대안 비교도 요청할 때만 적용하며 도착 시각은 반환된 출발 시각 기준의 예상값으로 안내합니다.
- 미래 출발 시각을 명시한 자동차 요청은 해당 출발 시각 기준의 교통 예측으로 안내합니다.
- 대중교통 결과가 없더라도 도보·자전거·자동차로 자동 전환하지 않습니다.
- 목적지 후보가 여러 개면 장소를 확인한 뒤 경로를 조회합니다.
- 선택한 대중교통 경로의 안내 문구에 지하철 출입구 번호가 명시되면 해당 역의 진입·진출 안내에 포함합니다.
- 다른 후보의 출구 번호를 가져오거나 정류장 이름만으로 추천 출구를 추정하지 않습니다. 정보가 없으면 생략합니다.
- 환승 도보 거리·시간은 요청하지 않으면 별도로 나열하지 않으며 전체 소요 시간에 다시 더하지 않습니다.

| 요청 예시 | 사용할 이동 수단 |
| --- | --- |
| "집에서 서울역까지 얼마나 걸려?" | 대중교통 `public_transport` |
| "거기까지 걸어서 가면?" | 도보 `walk` |
| "자전거로 가는 길 알려줘" | 자전거 `bicycle` |
| "차로 가는 길 알려줘" | 자동차 `car`, 추천 경로 |
| "차로 가장 빨리 가는 길" | 자동차 `car`, `priority: TIME` |
| "차로 통행료 피해서 가는 길" | 자동차 `car`, `avoid: [toll]` |
| "주유소 들렀다가 차로 가줘" | 자동차 `car`, 검색해 확인한 경유지 좌표를 `waypoints`로 전달 |
| "자동차 다른 경로도 비교해줘" | 자동차 `car`, `alternatives: true` |
| "내일 오전 8시에 차로 출발하면?" | 자동차 `car`, 날짜·시간대를 포함해 해석한 `departure_time` |

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
통합 버전은 `1.0.0`이며, HACS 최소 Home Assistant 버전은 `2026.10.1`입니다.

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

사용자 승인에 따라 이번 작업은 원격 push 대신 로컬 `dev` 커밋으로 백업합니다.
원격 저장소 연결 후 기존 작업 지침에 따라 dev push 절차를 적용합니다.
HACS 배포 전에는 실제 메타데이터, 공개 GitHub 저장소, 설명/토픽,
브랜드 요건 및 HACS/HA 검증 결과를 확인해야 합니다.

## 문제 제보

재현 단계와 Home Assistant 및 KakaoMap 버전을 GitHub 이슈에 남겨 주세요.
로그를 첨부할 때는 인증 정보와 개인 위치 정보를 지워 주세요. [GitHub Issues](https://github.com/plplaaa2/kakao_map_assist/issues)

## 후원

KakaoMap과 ipTIME Manager 개발을 같은 Ko-fi 계정에서 후원할 수 있습니다. [Ko-fi로 후원하기](https://ko-fi.com/plplaaa2)

## 공식 참고 문서

- [카카오맵 API 소개와 활성화](https://developers.kakao.com/docs/ko/kakaomap/common#rest-api)
- [카카오맵 REST API](https://developers.kakao.com/docs/ko/kakaomap/rest-api)
- [카카오모빌리티 자동차 길찾기 API](https://developers.kakaomobility.com/guide/navi-api/directions)
- [카카오모빌리티 미래 운행 정보 길찾기 API](https://developers.kakaomobility.com/guide/navi-api/future.html)
- [카카오 지도 길찾기 URL](https://apis.map.kakao.com/web/guide/#routeurl)
- [Home Assistant 응답 액션](https://developers.home-assistant.io/docs/dev_101_services/)
- [Home Assistant LLM 도구 및 API 등록](https://developers.home-assistant.io/docs/core/llm/)
- [HACS 통합 요구사항](https://www.hacs.dev/docs/publish/integration/)
- [HACS 공통 요구사항 및 hacs.json](https://hacs.dev/docs/publish/start/)
- [Home Assistant 통합 파일 구조](https://developers.home-assistant.io/docs/creating_integration_file_structure/)
- [Home Assistant manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/)
