import BottomNav from "./BottomNav";
import TopNav from "./TopNav";

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background-dark">
      <div className="hidden md:block">
        <TopNav />
      </div>

      <main className="px-6 pb-24 md:px-20 md:pb-8">{children}</main>

      <div className="md:hidden">
        <BottomNav />
      </div>
    </div>
  );
}

