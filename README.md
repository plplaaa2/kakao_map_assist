# KakaoMap

Home Assistant에서 사용할 HACS 커스텀 통합의 초기 개발 골격입니다.
현재는 기능, 설정 흐름, 엔티티 및 API 연동이 구현되지 않았습니다.
설치 또는 통합 추가를 통한 실제 사용은 아직 지원하지 않습니다.

## 기본 구조

실행에 필요한 파일은 `custom_components/kakaomap/`에 배치합니다.
`manifest.json`은 Home Assistant 메타데이터이며, 루트의 `hacs.json`은
HACS 표시 이름과 README 렌더링을 설정합니다. 전체 구조는 `tree.md`를 참고하세요.

## 구현 전에 결정할 사항

- 제공할 기능과 엔티티 종류, 사용할 API 및 인증 방식
- GitHub 저장소 주소와 관리자 계정
- 지원할 Home Assistant 최소 버전과 실제 배포 버전
- 라이선스와 브랜드 이미지

`manifest.json`의 `example.com` 주소는 교체가 필요한 자리표시자입니다.
`codeowners`에는 실제 GitHub 관리자를 등록해야 합니다.
`version`의 `0.0.0`은 커스텀 통합의 필수 필드를 위한 자리표시자이며,
공식 배포 버전은 사용자 지정 후 확정합니다. 최소 지원 버전과 IoT 분류는
구현 및 검증 후 설정합니다.

## 이후 확장할 파일

UI 설정을 구현할 때 `config_flow.py`, `strings.json`, `translations/ko.json`,
`translations/en.json`을 추가하고 `config_flow`를 활성화합니다.
데이터 갱신 방식에 따라 `coordinator.py`, 엔티티 종류에 따라 `sensor.py` 등
플랫폼 파일을 추가합니다. 서비스 액션을 제공하면 `services.yaml`을 추가합니다.
테스트는 구현된 동작에 맞춰 `tests/`에 작성합니다.

## 개발 관리

로직 구현 전 변경 파일과 단계별 계획을 승인받습니다.
소스와 문서는 UTF-8 BOM 없이 유지하고, 비밀 값은 소스나 로그에 기록하지 않습니다.
애플리케이션 로그의 기본 수준은 INFO로 하고 필요에 따라 WARN, ERROR, DEBUG를 구분합니다.
변경 이력은 `changelog.jsonl`, 주의사항은 `caution.jsonl`에서 관리합니다.

현재 폴더에는 Git 저장소 및 원격 저장소가 없어 dev 브랜치 push를 수행할 수 없습니다.
저장소 설정 후 기존 작업 지침에 따라 dev 백업 및 push 절차를 적용합니다.
HACS 배포 전에는 실제 메타데이터, 공개 GitHub 저장소, 설명/토픽,
브랜드 요건 및 HACS/HA 검증 결과를 확인해야 합니다.

## 공식 참고 문서

- [HACS 통합 요구사항](https://www.hacs.dev/docs/publish/integration/)
- [HACS 공통 요구사항 및 hacs.json](https://hacs.dev/docs/publish/start/)
- [Home Assistant 통합 파일 구조](https://developers.home-assistant.io/docs/creating_integration_file_structure/)
- [Home Assistant manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/)
