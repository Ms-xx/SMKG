import { useState, useCallback } from "react";

export function usePagination({ initialPage = 1, initialPageSize = 10 } = {}) {
  const [page, setPage] = useState(initialPage);
  const [pageSize, setPageSize] = useState(initialPageSize);

  const pagination = useCallback(
    (onChange: (page: number, pageSize: number) => void) => ({
      current: page,
      pageSize,
      showSizeChanger: true,
      showQuickJumper: true,
      showTotal: (total: number) => `共 ${total} 条`,
      onChange: (newPage: number, newPageSize: number) => {
        setPage(newPage);
        setPageSize(newPageSize);
        onChange(newPage, newPageSize);
      },
    }),
    [page, pageSize],
  );

  const reset = useCallback(() => {
    setPage(initialPage);
    setPageSize(initialPageSize);
  }, [initialPage, initialPageSize]);

  return { page, pageSize, setPage, setPageSize, pagination, reset };
}
