import csv
from pathlib import Path


# =========================================================
# 1. 프로젝트 경로 설정
# =========================================================
BASE_DIR = Path(__file__).resolve().parent.parent

TRACKING_PATH = (
    BASE_DIR
    / "data"
    / "outputs"
    / "pet_tracking_data_stable.csv"
)

OUTPUT_PATH = (
    BASE_DIR
    / "data"
    / "outputs"
    / "space_analysis.csv"
)


# =========================================================
# 2. ROI 설정
# =========================================================
# 형식:
# "이름": (x1, y1, x2, y2)
#
# 현재는 테스트용 값
# 영상 확인 후 실제 위치에 맞게 수정해야 함
ROIS = {

    "BED": (
        700,
        500,
        1050,
        750
    ),

    "WATER": (
        1450,
        500,
        1750,
        800
    ),

    "CENTER": (
        900,
        350,
        1350,
        750
    )
}


# =========================================================
# 3. 좌표가 ROI 내부인지 확인
# =========================================================
def is_inside_roi(
    x,
    y,
    roi
):

    x1, y1, x2, y2 = roi

    return (
        x1 <= x <= x2
        and
        y1 <= y <= y2
    )


# =========================================================
# 4. Tracking CSV 읽기
# =========================================================
if not TRACKING_PATH.exists():

    raise FileNotFoundError(
        f"Tracking CSV를 찾을 수 없습니다.\n"
        f"{TRACKING_PATH}"
    )


tracking_data = []


with open(
    TRACKING_PATH,
    "r",
    encoding="utf-8"
) as csvfile:

    reader = csv.DictReader(
        csvfile
    )

    for row in reader:

        if (
            row["center_x"] == ""
            or
            row["center_y"] == ""
        ):
            continue


        tracking_data.append({

            "frame":
                int(
                    row["frame"]
                ),

            "time_sec":
                float(
                    row["time_sec"]
                ),

            "center_x":
                float(
                    row["center_x"]
                ),

            "center_y":
                float(
                    row["center_y"]
                )
        })


if len(tracking_data) < 2:

    raise ValueError(
        "공간 분석을 위한 Tracking 데이터가 부족합니다."
    )


# =========================================================
# 5. ROI별 통계 초기화
# =========================================================
space_stats = {}


for roi_name in ROIS:

    space_stats[
        roi_name
    ] = {

        "visit_count": 0,

        "stay_time_sec": 0.0,

        "inside_previous": False
    }


# =========================================================
# 6. 프레임별 공간 분석
# =========================================================
for i in range(
    len(tracking_data)
):

    current = (
        tracking_data[i]
    )


    if i == 0:

        delta_time = 0.0

    else:

        previous = (
            tracking_data[
                i - 1
            ]
        )

        delta_time = (
            current["time_sec"]
            -
            previous["time_sec"]
        )


    for (
        roi_name,
        roi
    ) in ROIS.items():

        inside = is_inside_roi(

            current["center_x"],

            current["center_y"],

            roi
        )


        stats = (
            space_stats[
                roi_name
            ]
        )


        # -----------------------------------------
        # 새롭게 ROI에 들어온 순간
        # -----------------------------------------
        if (
            inside
            and
            not stats[
                "inside_previous"
            ]
        ):

            stats[
                "visit_count"
            ] += 1


        # -----------------------------------------
        # ROI 내부 체류시간
        # -----------------------------------------
        if inside:

            stats[
                "stay_time_sec"
            ] += max(
                delta_time,
                0.0
            )


        stats[
            "inside_previous"
        ] = inside


# =========================================================
# 7. 전체 영상 길이
# =========================================================
start_time = (
    tracking_data[0][
        "time_sec"
    ]
)

end_time = (
    tracking_data[-1][
        "time_sec"
    ]
)

duration_sec = (
    end_time
    -
    start_time
)


# =========================================================
# 8. 체류 비율 계산
# =========================================================
results = []


for roi_name in ROIS:

    stats = (
        space_stats[
            roi_name
        ]
    )


    stay_time = (
        stats[
            "stay_time_sec"
        ]
    )


    if duration_sec > 0:

        stay_ratio = (
            stay_time
            /
            duration_sec
        )

    else:

        stay_ratio = 0.0


    results.append({

        "roi":
            roi_name,

        "visit_count":
            stats[
                "visit_count"
            ],

        "stay_time_sec":
            stay_time,

        "stay_ratio":
            stay_ratio
    })


# =========================================================
# 9. CSV 저장
# =========================================================
OUTPUT_PATH.parent.mkdir(
    parents=True,
    exist_ok=True
)


with open(
    OUTPUT_PATH,
    "w",
    newline="",
    encoding="utf-8"
) as csvfile:

    writer = csv.writer(
        csvfile
    )


    writer.writerow([
        "roi",
        "visit_count",
        "stay_time_sec",
        "stay_ratio"
    ])


    for result in results:

        writer.writerow([

            result[
                "roi"
            ],

            result[
                "visit_count"
            ],

            round(
                result[
                    "stay_time_sec"
                ],
                3
            ),

            round(
                result[
                    "stay_ratio"
                ],
                6
            )
        ])


# =========================================================
# 10. 결과 출력
# =========================================================
print(
    "==================================="
)

print(
    "PET SPACE ANALYSIS"
)

print(
    "==================================="
)

print(
    f"Duration : "
    f"{duration_sec:.2f} sec"
)

print()


for result in results:

    print(
        f"[{result['roi']}]"
    )

    print(
        f"  Visit Count : "
        f"{result['visit_count']}"
    )

    print(
        f"  Stay Time   : "
        f"{result['stay_time_sec']:.2f} sec"
    )

    print(
        f"  Stay Ratio  : "
        f"{result['stay_ratio']:.3f}"
    )

    print()


print(
    "==================================="
)

print(
    "SPACE ANALYSIS COMPLETE"
)

print(
    "==================================="
)

print(
    "Saved CSV:"
)

print(
    OUTPUT_PATH
)