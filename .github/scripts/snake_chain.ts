import { readFileSync, writeFileSync } from "node:fs";
import { getBestRoute } from "../solver/getBestRoute";
import { getPathToPose } from "../solver/getPathToPose";
import { snake4 } from "../types/__fixtures__/snake";
import { createEmptyGrid, setColor, setColorEmpty } from "../types/grid";
import { getHeadX, getHeadY } from "../types/snake";

const L: Record<string, number> = { NONE: 0, FIRST_QUARTILE: 1, SECOND_QUARTILE: 2, THIRD_QUARTILE: 3, FOURTH_QUARTILE: 4 };
let d = JSON.parse(readFileSync(process.argv[2], "utf8"));
if (d.data) d = d.data.user.contributionsCollection.contributionCalendar.weeks;
else if (d.weeks) d = d.weeks;
const cells: { x: number; y: number; level: number }[] = [];
d.forEach((w: any, x: number) => w.contributionDays.forEach((c: any) => cells.push({ x, y: c.weekday, level: L[c.contributionLevel] })));
const grid = createEmptyGrid(Math.max(...cells.map((c) => c.x)) + 1, 7);
for (const c of cells) c.level > 0 ? setColor(grid, c.x, c.y, c.level as any) : setColorEmpty(grid, c.x, c.y);
const chain = getBestRoute(grid, snake4)!;
chain.push(...getPathToPose(chain.slice(-1)[0], snake4)!);
writeFileSync(process.argv[3], JSON.stringify(chain.map((s) => [getHeadX(s), getHeadY(s)])));
console.log("chain", chain.length);
