/** Dubai skyline silhouette for the hero (original artwork, drawn in code: no licence to clear). */
export function Skyline({ className }: { className?: string }) {
  // [x, width, height] towers, plus the Burj Khalifa drawn as a stepped spire
  const towers: [number, number, number][] = [
    [10, 26, 70], [40, 18, 95], [62, 30, 60], [96, 22, 120], [122, 16, 85], [142, 34, 140], [180, 20, 105], [204, 28, 75],
    [236, 18, 160], [258, 26, 110], [290, 14, 90], [308, 30, 130], [342, 22, 95], [520, 24, 115], [548, 30, 150], [582, 18, 100],
    [604, 26, 175], [634, 20, 120], [658, 32, 90], [694, 22, 140], [720, 18, 105], [742, 28, 80], [774, 20, 125], [798, 26, 95],
  ];
  return (
    <svg viewBox="0 0 830 300" preserveAspectRatio="xMaxYMax meet" className={className} aria-hidden>
      <defs>
        <linearGradient id="sky-fade" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#163a6b" stopOpacity="0.55" />
          <stop offset="1" stopColor="#163a6b" stopOpacity="0.85" />
        </linearGradient>
      </defs>
      <g fill="url(#sky-fade)">
        {towers.map(([x, w, h], i) => <rect key={i} x={x} y={300 - h} width={w} height={h} rx={i % 3 === 0 ? 3 : 1} />)}
        {/* Burj Khalifa */}
        <path d="M430 300 L430 230 L436 230 L436 170 L441 170 L441 110 L445 110 L445 60 L448 60 L449 8 L450 60 L453 60 L453 110 L457 110 L457 170 L462 170 L462 230 L468 230 L468 300 Z" />
        {/* Burj Al Arab sail */}
        <path d="M372 300 L372 150 Q410 190 402 300 Z" opacity="0.8" />
      </g>
      <rect x="0" y="292" width="830" height="8" fill="#163a6b" opacity="0.85" />
    </svg>
  );
}
