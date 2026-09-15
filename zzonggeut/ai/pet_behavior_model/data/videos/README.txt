[분석 영상 저장 폴더]

분석할 강아지·고양이 영상 파일을 이 폴더에 저장합니다.

[포함된 테스트 영상]
- pet_tracking_test.mp4: 강아지 정상 분석 테스트용
- cat_tracking_test2.mp4: 고양이 정상 분석 테스트용

[지원 영상 형식]
- MP4 (.mp4)
- MOV (.mov)
- AVI (.avi)
- MKV (.mkv)

[실행 예시]
강아지:
python src/run_pipeline.py data/videos/pet_tracking_test.mp4 dog

고양이:
python src/run_pipeline.py data/videos/cat_tracking_test2.mp4 cat

테스트 영상 2개는 모델과 백엔드의 연동 및 정상 분석 흐름을 확인하기 위해 포함했습니다.
그 외 원본·검증 영상은 프로젝트 외부 백업 폴더에 보관합니다.
