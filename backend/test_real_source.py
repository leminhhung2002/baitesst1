"""Kiểm tra adapter real.py độc lập, KHÔNG cần Postgres.

Cách chạy:
    cd backend
    export REAL_API_BASE_URL=https://api.provider.com
    export REAL_API_KEY=xxxx
    export DATA_SOURCE=real
    python test_real_source.py

Mục tiêu: xác nhận lấy được dữ liệu và map đúng field TRƯỚC khi cắm vào hệ
thống. Nếu in ra 3 KOC có đủ tên/follower/doanh thu -> adapter OK.
"""
from app.sources.real import RealApiDataSource


def main():
    recs = RealApiDataSource().fetch()
    print(f"\nTổng số bản ghi: {len(recs)}\n")
    for r in recs[:3]:
        print("-" * 50)
        print(f"id        : {r.platform_user_id}")
        print(f"tên       : {r.display_name}  ({r.username})")
        print(f"follower  : {r.follower_count:,}")
        print(f"doanh thu : {r.revenue} {r.currency} / {r.revenue_period}")
        print(f"avatar    : {r.avatar_url}")
        print(f"kênh      : {r.channel_url}")

    # cảnh báo nếu field quan trọng rỗng -> dấu hiệu map sai
    if recs:
        miss = [k for k, v in {
            "display_name": recs[0].display_name == "Unknown",
            "follower_count": recs[0].follower_count == 0,
            "revenue": recs[0].revenue is None,
        }.items() if v]
        if miss:
            print(f"\n[!] Field nghi ngờ map sai: {miss} "
                  f"-> kiểm tra lại [SỬA #4] trong real.py")
        else:
            print("\n[OK] Mapping trông hợp lệ.")


if __name__ == "__main__":
    main()
