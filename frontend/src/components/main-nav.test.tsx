import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/mistakes" }));

import { MainNav } from "./main-nav";

describe("MainNav", () => {
  beforeEach(() => render(<MainNav />));

  it("shows V3 primary and secondary routes without duplicate feature links", () => {
    const nav = screen.getByRole("navigation", { name: "Điều hướng chính" });
    expect(nav).toHaveTextContent("Tổng quan");
    expect(nav).toHaveTextContent("Kho đề");
    expect(nav).toHaveTextContent("Phân tích JLPT");
    expect(nav).toHaveTextContent("Học tập");
    expect(nav).toHaveTextContent("Cài đặt");
    expect(nav).toHaveTextContent("Hướng dẫn sử dụng");
    expect(nav).not.toHaveTextContent("Nhập đề");
    expect(nav).not.toHaveTextContent("Lịch sử bài làm");
    expect(nav).not.toHaveTextContent("Ôn tập");
    expect(nav).not.toHaveTextContent("Kho kiến thức");
    expect(nav).not.toHaveTextContent("Sổ lỗi sai");
    expect(nav.querySelectorAll("a")).toHaveLength(6);
    expect(Array.from(nav.querySelectorAll("a")).map((link) => link.getAttribute("href"))).toEqual([
      "/", "/learning", "/exams", "/analytics/jlpt", "/settings", "/help",
    ]);
  });
});
