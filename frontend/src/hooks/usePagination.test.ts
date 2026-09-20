import { describe, it, expect, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { usePagination } from "./usePagination";

describe("usePagination", () => {
  it("使用默认初始值", () => {
    const { result } = renderHook(() => usePagination());
    expect(result.current.page).toBe(1);
    expect(result.current.pageSize).toBe(10);
  });

  it("使用自定义初始值", () => {
    const { result } = renderHook(() => usePagination({ initialPage: 2, initialPageSize: 20 }));
    expect(result.current.page).toBe(2);
    expect(result.current.pageSize).toBe(20);
  });

  it("setPage / setPageSize 更新状态", () => {
    const { result } = renderHook(() => usePagination());
    act(() => result.current.setPage(5));
    act(() => result.current.setPageSize(50));
    expect(result.current.page).toBe(5);
    expect(result.current.pageSize).toBe(50);
  });

  it("pagination.onChange 触发回调并更新状态", () => {
    const onChange = vi.fn();
    const { result } = renderHook(() => usePagination());

    const paginationConfig = result.current.pagination(onChange);
    act(() => paginationConfig.onChange(3, 30));

    expect(onChange).toHaveBeenCalledWith(3, 30);
    expect(result.current.page).toBe(3);
    expect(result.current.pageSize).toBe(30);
  });

  it("reset 恢复初始值", () => {
    const { result } = renderHook(() => usePagination({ initialPage: 1, initialPageSize: 10 }));
    act(() => result.current.setPage(7));
    act(() => result.current.setPageSize(100));
    act(() => result.current.reset());
    expect(result.current.page).toBe(1);
    expect(result.current.pageSize).toBe(10);
  });
});
