import {
  Users, Package, Receipt, ShoppingCart, Wallet, IdCard, Pencil, Trash2, Check, Plus, Sparkles, CircleCheck,
  LayoutDashboard, ChartColumn, Info, TriangleAlert, TrendingUp, TrendingDown, Search, X, Zap, Bot, type LucideIcon,
} from "lucide-react";

const MAP: Record<string, LucideIcon> = {
  users: Users, package: Package, receipt: Receipt, "shopping-cart": ShoppingCart, wallet: Wallet, "id-card": IdCard,
  pencil: Pencil, trash: Trash2, check: Check, plus: Plus, sparkles: Sparkles, "check-circle": CircleCheck,
  dashboard: LayoutDashboard, chart: ChartColumn, info: Info, warning: TriangleAlert, "trending-up": TrendingUp,
  "trending-down": TrendingDown, search: Search, close: X, zap: Zap, bot: Bot,
};

export function Icon({ name, className = "h-4 w-4" }: { name?: string; className?: string }) {
  const C = (name && MAP[name]) || Sparkles;
  return <C className={className} strokeWidth={2} />;
}
