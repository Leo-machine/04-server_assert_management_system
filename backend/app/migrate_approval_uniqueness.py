"""为审批流补齐「每个配件最多一张在途单」的 SQLite 约束。"""

from sqlalchemy import text
from sqlalchemy.orm import Session


def migrate_approval_uniqueness(db: Session) -> None:
    # 历史数据若已有重复在途单，保留最早一张，其余系统作废。
    duplicate_parts = db.execute(
        text(
            "SELECT part_id FROM approval WHERE overall_status = '审批中' "
            "GROUP BY part_id HAVING COUNT(*) > 1"
        )
    ).scalars().all()
    for part_id in duplicate_parts:
        rows = db.execute(
            text(
                "SELECT id FROM approval WHERE part_id = :part_id "
                "AND overall_status = '审批中' ORDER BY id"
            ),
            {"part_id": part_id},
        ).scalars().all()
        for approval_id in rows[1:]:
            db.execute(
                text(
                    "UPDATE approval SET overall_status = '驳回', "
                    "remark = COALESCE(remark, '') || '【系统作废】历史重复在途审批' "
                    "WHERE id = :approval_id"
                ),
                {"approval_id": approval_id},
            )
    db.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_approval_pending_part "
            "ON approval(part_id) WHERE overall_status = '审批中'"
        )
    )
    db.commit()
