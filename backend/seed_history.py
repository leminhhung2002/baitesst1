"""Seed LỊCH SỬ SNAPSHOT mô phỏng để biểu đồ tăng trưởng có dữ liệu.

Vì sao cần: biểu đồ trong trang chi tiết vẽ từ bảng koc_snapshot. Khi mới seed,
mỗi KOC chỉ có 1 snapshot -> biểu đồ báo "chưa đủ dữ liệu". Script này tạo
N điểm lịch sử (mặc định 8 tuần) dẫn dần tới số follower/doanh thu HIỆN TẠI.

LƯU Ý: đây là lịch sử *giả lập cho demo* (không có nguồn miễn phí cho lịch sử
follower thật). Đường tăng trưởng sinh theo hash(handle) -> ỔN ĐỊNH, chạy lại
không đổi. Khi đồng bộ thật theo thời gian, snapshot thật sẽ tự tích lũy thêm.

Chạy:  python seed_history.py            # 8 điểm/tuần
       python seed_history.py 12 5       # 12 điểm, mỗi điểm cách 5 ngày
"""
import hashlib
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.database import SessionLocal
from app.models import Koc, KocSnapshot


def seed(points: int = 8, step_days: int = 7) -> None:
    db = SessionLocal()
    try:
        kocs = db.query(Koc).all()
        now = datetime.now(timezone.utc)
        total = 0
        for k in kocs:
            cur_f = int(k.follower_count or 0)
            cur_r = float(k.revenue or 0)
            if cur_f <= 0:
                continue

            # hệ số khởi điểm 0.80..0.92 theo hash(handle) -> ổn định, mỗi KOC
            # một đà tăng hơi khác nhau cho biểu đồ sinh động.
            h = int(hashlib.sha256(k.platform_user_id.encode()).hexdigest(), 16)
            start_factor = 0.80 + (h % 13) / 100        # 0.80 .. 0.92

            # xoá snapshot cũ rồi dựng chuỗi mới kết thúc ĐÚNG giá trị hiện tại
            db.query(KocSnapshot).filter(KocSnapshot.koc_id == k.id).delete()
            for i in range(points):
                frac = i / (points - 1)                 # 0 -> 1
                # nhịp tăng + nhiễu nhỏ deterministic để đường không phẳng lì
                jitter = 1 + (((h >> (i + 1)) % 7) - 3) / 1000   # ±0.3%
                if i == points - 1:
                    f_i, r_i = cur_f, cur_r              # điểm cuối = hiện tại
                else:
                    scale = start_factor + (1 - start_factor) * frac
                    f_i = int(cur_f * scale * jitter)
                    r_i = round(cur_r * scale * jitter, 2)
                captured = now - timedelta(days=step_days * (points - 1 - i))
                db.add(KocSnapshot(koc_id=k.id, follower_count=f_i,
                                   revenue=Decimal(str(r_i)), captured_at=captured))
                total += 1
        db.commit()
        print(f"Seed lịch sử: {total} snapshot cho {len(kocs)} KOC "
              f"({points} điểm, cách nhau {step_days} ngày).")
    finally:
        db.close()


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    d = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    seed(points=max(n, 2), step_days=max(d, 1))
