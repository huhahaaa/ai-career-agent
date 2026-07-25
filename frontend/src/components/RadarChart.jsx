import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart as RechartsRadar, ResponsiveContainer } from 'recharts';

export default function RadarChart({ data = [], height = 300 }) {
  const chartData = data.map((d) => ({
    name: d.name,
    value: d.score,
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RechartsRadar data={chartData} cx="50%" cy="50%" outerRadius="75%">
        <PolarGrid />
        <PolarAngleAxis dataKey="name" tick={{ fontSize: 12 }} />
        <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 10 }} />
        <Radar
          name="评分"
          dataKey="value"
          stroke="#6366f1"
          fill="#6366f1"
          fillOpacity={0.2}
        />
      </RechartsRadar>
    </ResponsiveContainer>
  );
}
