import { useEffect, useState } from "react";
import { api } from "../api/client";
type W = { bag_id: number; bag_index: number; route_id: number; weight_kg: number; volume_l: number; max_weight_kg: number; max_volume_l: number; fill_weight_pct: number; fill_volume_pct: number; remaining_weight_kg: number; remaining_volume_l: number };
export default function WeightsPage() {
  const [rows, setRows] = useState<W[]>([]);
  useEffect(() => { api<W[]>("/weights").then(setRows); }, []);
  return (<>
    <h2>袋重</h2>
    <table className="table"><thead><tr><th>袋</th><th>路线</th><th>已装重量</th><th>重量上限</th><th>重量填充</th><th>剩余可装重量</th><th>已装体积</th><th>体积上限</th><th>体积填充</th><th>剩余可装体积</th></tr></thead>
    <tbody>{rows.map(w => <tr key={w.bag_id}><td>{w.bag_index}</td><td>{w.route_id}</td>
      <td className="mono">{w.weight_kg}kg</td><td className="mono">{w.max_weight_kg}kg</td>
      <td><div className="fill"><span style={{ width: `${Math.min(100, w.fill_weight_pct)}%` }} /></div><span className="mono">{w.fill_weight_pct}%</span></td>
      <td className="mono">{w.remaining_weight_kg}kg</td>
      <td className="mono">{w.volume_l}L</td><td className="mono">{w.max_volume_l}L</td>
      <td><div className="fill"><span style={{ width: `${Math.min(100, w.fill_volume_pct)}%` }} /></div><span className="mono">{w.fill_volume_pct}%</span></td>
      <td className="mono">{w.remaining_volume_l}L</td>
    </tr>)}
      {!rows.length && <tr><td colSpan={10}>尚无装袋结果，请先执行装袋</td></tr>}
    </tbody></table>
  </>);
}
