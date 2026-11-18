import Link from "next/link";

import { EmptyState } from "@/components/states";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <EmptyState
      title="Không tìm thấy trang"
      action={
        <Button asChild variant="outline">
          <Link href="/">Về Tổng quan</Link>
        </Button>
      }
    />
  );
}
