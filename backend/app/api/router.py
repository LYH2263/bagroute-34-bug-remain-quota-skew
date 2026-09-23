from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import BagItem, DeliveryRoute, PackBag, RejectRecord, SubscriberStop
from app.schemas.schemas import (
    BagItemOut,
    BagOut,
    PackRequest,
    RejectOut,
    RouteOut,
    StopOut,
    WeightOut,
)
from app.services.pack_engine import StopItem, bag_load_stats, pack_route

api_router = APIRouter()


@api_router.get("/health")
def health():
    return {"status": "ok"}


@api_router.get("/routes", response_model=list[RouteOut])
def routes(db: Session = Depends(get_db)):
    return db.scalars(select(DeliveryRoute).order_by(DeliveryRoute.id)).all()


@api_router.get("/stops", response_model=list[StopOut])
def stops(route_id: int | None = None, db: Session = Depends(get_db)):
    q = select(SubscriberStop).order_by(SubscriberStop.route_id, SubscriberStop.seq)
    if route_id is not None:
        q = q.where(SubscriberStop.route_id == route_id)
    return db.scalars(q).all()


@api_router.post("/pack", response_model=list[BagOut])
def pack(body: PackRequest, db: Session = Depends(get_db)):
    route = db.get(DeliveryRoute, body.route_id)
    if not route:
        raise HTTPException(404, "路线不存在")
    # clear previous pack for route
    old_bags = db.scalars(select(PackBag).where(PackBag.route_id == route.id)).all()
    for b in old_bags:
        for it in list(b.items):
            db.delete(it)
        db.delete(b)
    old_rej = db.scalars(select(RejectRecord).where(RejectRecord.route_id == route.id)).all()
    for r in old_rej:
        db.delete(r)
    db.flush()

    stops = db.scalars(
        select(SubscriberStop).where(SubscriberStop.route_id == route.id).order_by(SubscriberStop.seq)
    ).all()
    items = [
        StopItem(s.id, s.seq, s.weight_kg, s.volume_l, s.name) for s in stops
    ]
    result = pack_route(items, route.max_weight_kg, route.max_volume_l)
    out_bags: list[PackBag] = []
    for bag in result.bags:
        # 袋重/袋体积以袋内各订户点明细求和为准落库，与袋明细页同源
        bag_weight = round(sum(it.weight_kg for it in bag.items), 3)
        bag_volume = round(sum(it.volume_l for it in bag.items), 3)
        row = PackBag(
            route_id=route.id,
            bag_index=bag.bag_index,
            weight_kg=bag_weight,
            volume_l=bag_volume,
        )
        db.add(row)
        db.flush()
        for it in bag.items:
            db.add(
                BagItem(
                    bag_id=row.id,
                    stop_id=it.stop_id,
                    stop_name=it.label,
                    weight_kg=it.weight_kg,
                    volume_l=it.volume_l,
                )
            )
        out_bags.append(row)
    for stop, reason in result.rejects:
        db.add(
            RejectRecord(
                route_id=route.id,
                stop_id=stop.stop_id,
                stop_name=stop.label,
                reason=reason,
            )
        )
    db.commit()
    return [
        BagOut(
            id=b.id,
            route_id=b.route_id,
            bag_index=b.bag_index,
            weight_kg=b.weight_kg,
            volume_l=b.volume_l,
            items=[
                BagItemOut(
                    stop_id=i.stop_id,
                    stop_name=i.stop_name,
                    weight_kg=i.weight_kg,
                    volume_l=i.volume_l,
                )
                for i in db.scalars(select(BagItem).where(BagItem.bag_id == b.id)).all()
            ],
        )
        for b in out_bags
    ]


@api_router.get("/bags", response_model=list[BagOut])
def bags(db: Session = Depends(get_db)):
    rows = db.scalars(select(PackBag).order_by(PackBag.route_id, PackBag.bag_index)).all()
    out = []
    for b in rows:
        items = db.scalars(select(BagItem).where(BagItem.bag_id == b.id)).all()
        out.append(
            BagOut(
                id=b.id,
                route_id=b.route_id,
                bag_index=b.bag_index,
                weight_kg=b.weight_kg,
                volume_l=b.volume_l,
                items=[
                    BagItemOut(
                        stop_id=i.stop_id,
                        stop_name=i.stop_name,
                        weight_kg=i.weight_kg,
                        volume_l=i.volume_l,
                    )
                    for i in items
                ],
            )
        )
    return out


@api_router.get("/rejects", response_model=list[RejectOut])
def rejects(db: Session = Depends(get_db)):
    return db.scalars(select(RejectRecord).order_by(RejectRecord.id.desc())).all()


@api_router.get("/weights", response_model=list[WeightOut])
def weights(db: Session = Depends(get_db)):
    # 每个袋是路线上的独立装载单位，路线上限即每袋容量上限（与装袋判定同口径）。
    # 剩余额度 = 该袋所属路线上限 - 该袋已装；填充比例 = 该袋已装 / 路线上限。
    # 袋重取 pack_bags 落库值，与袋明细同表同源；路线上限每次请求实时读取，
    # 上限变更生效后剩余与填充随刷新即按新上限计算。
    out: list[WeightOut] = []
    routes = db.scalars(select(DeliveryRoute).order_by(DeliveryRoute.id)).all()
    for route in routes:
        bags = db.scalars(
            select(PackBag)
            .where(PackBag.route_id == route.id)
            .order_by(PackBag.bag_index)
        ).all()
        for b in bags:
            stats = bag_load_stats(
                b.weight_kg, b.volume_l, route.max_weight_kg, route.max_volume_l
            )
            out.append(
                WeightOut(
                    bag_id=b.id,
                    bag_index=b.bag_index,
                    route_id=b.route_id,
                    weight_kg=b.weight_kg,
                    volume_l=b.volume_l,
                    fill_weight_pct=stats.fill_weight_pct,
                    fill_volume_pct=stats.fill_volume_pct,
                    remaining_weight_kg=stats.remaining_weight_kg,
                    remaining_volume_l=stats.remaining_volume_l,
                )
            )
    return out
