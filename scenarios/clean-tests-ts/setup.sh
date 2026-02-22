#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

mkdir -p src __tests__

cat > src/math.ts << 'TS'
export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

export function roundTo(value: number, decimals: number): number {
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
}

export function sum(values: number[]): number {
  return values.reduce((acc, v) => acc + v, 0);
}

export function mean(values: number[]): number {
  if (values.length === 0) throw new Error("Cannot compute mean of empty array");
  return sum(values) / values.length;
}
TS

cat > src/strings.ts << 'TS'
export function slugify(input: string): string {
  return input
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, "")
    .replace(/[\s_]+/g, "-")
    .replace(/-+/g, "-");
}

export function truncate(input: string, maxLength: number, suffix = "..."): string {
  if (input.length <= maxLength) return input;
  return input.slice(0, maxLength - suffix.length) + suffix;
}

export function capitalize(input: string): string {
  if (input.length === 0) return input;
  return input.charAt(0).toUpperCase() + input.slice(1);
}
TS

git add -A && git commit -q -m "init: math and string utility modules"

# Add comprehensive tests for existing code — clean, no bugs
cat > __tests__/math.test.ts << 'TS'
import { clamp, lerp, roundTo, sum, mean } from "../src/math";

describe("clamp", () => {
  it("returns value when within range", () => {
    expect(clamp(5, 0, 10)).toBe(5);
  });

  it("clamps to min when below range", () => {
    expect(clamp(-5, 0, 10)).toBe(0);
  });

  it("clamps to max when above range", () => {
    expect(clamp(15, 0, 10)).toBe(10);
  });

  it("handles equal min and max", () => {
    expect(clamp(5, 3, 3)).toBe(3);
  });
});

describe("lerp", () => {
  it("returns a when t is 0", () => {
    expect(lerp(10, 20, 0)).toBe(10);
  });

  it("returns b when t is 1", () => {
    expect(lerp(10, 20, 1)).toBe(20);
  });

  it("returns midpoint when t is 0.5", () => {
    expect(lerp(0, 100, 0.5)).toBe(50);
  });
});

describe("roundTo", () => {
  it("rounds to specified decimals", () => {
    expect(roundTo(3.14159, 2)).toBe(3.14);
  });

  it("rounds to zero decimals", () => {
    expect(roundTo(3.7, 0)).toBe(4);
  });
});

describe("sum", () => {
  it("sums an array of numbers", () => {
    expect(sum([1, 2, 3, 4])).toBe(10);
  });

  it("returns 0 for empty array", () => {
    expect(sum([])).toBe(0);
  });
});

describe("mean", () => {
  it("computes mean of numbers", () => {
    expect(mean([2, 4, 6])).toBe(4);
  });

  it("throws on empty array", () => {
    expect(() => mean([])).toThrow("Cannot compute mean of empty array");
  });
});
TS

cat > __tests__/strings.test.ts << 'TS'
import { slugify, truncate, capitalize } from "../src/strings";

describe("slugify", () => {
  it("converts spaces to hyphens", () => {
    expect(slugify("hello world")).toBe("hello-world");
  });

  it("lowercases input", () => {
    expect(slugify("Hello World")).toBe("hello-world");
  });

  it("strips special characters", () => {
    expect(slugify("hello! @world#")).toBe("hello-world");
  });

  it("collapses multiple hyphens", () => {
    expect(slugify("hello   world")).toBe("hello-world");
  });

  it("trims whitespace", () => {
    expect(slugify("  hello  ")).toBe("hello");
  });
});

describe("truncate", () => {
  it("returns input when shorter than max", () => {
    expect(truncate("hello", 10)).toBe("hello");
  });

  it("truncates with default suffix", () => {
    expect(truncate("hello world", 8)).toBe("hello...");
  });

  it("uses custom suffix", () => {
    expect(truncate("hello world", 7, "~")).toBe("hello ~");
  });
});

describe("capitalize", () => {
  it("capitalizes first letter", () => {
    expect(capitalize("hello")).toBe("Hello");
  });

  it("handles empty string", () => {
    expect(capitalize("")).toBe("");
  });

  it("handles single character", () => {
    expect(capitalize("h")).toBe("H");
  });
});
TS
git add -A
