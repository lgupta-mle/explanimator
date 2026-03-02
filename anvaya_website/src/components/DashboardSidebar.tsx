import { Home, Video, Coins, MessageSquare } from "lucide-react";
import { NavLink } from "@/components/NavLink";
import { useNavigate } from "react-router-dom";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";

const items = [
  { title: "Home", url: "/dashboard", icon: Home },
  { title: "My Videos", url: "/videos", icon: Video },
  { title: "Tokens", url: "/tokens", icon: Coins },
  { title: "Feedback", url: "/feedback", icon: MessageSquare },
];

const DashboardSidebar = () => {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const navigate = useNavigate();

  return (
    <Sidebar collapsible="icon" className="border-r border-border/10 bg-sidebar">
      <SidebarContent className="pt-8">
        {/* Logo */}
        <div className={`mb-10 ${collapsed ? "px-0 flex justify-center" : "px-4"}`}>
          <button
            onClick={() => navigate("/")}
            className={`transition-all hover:opacity-80 cursor-pointer ${collapsed ? "flex items-center justify-center w-full" : "w-full text-left"}`}
          >
            {collapsed ? (
              <span className="font-heading text-2xl text-gold-gradient">A</span>
            ) : (
              <div>
                <span className="font-heading text-2xl text-gold-gradient tracking-[0.25em] block">
                  ANVAYA
                </span>
                <span className="text-xs text-muted-foreground font-body tracking-widest mt-1 block opacity-60">
                  ACADEMY
                </span>
              </div>
            )}
          </button>
        </div>

        {/* Divider */}
        {!collapsed && (
          <div className="mx-4 mb-6 h-px bg-gradient-to-r from-transparent via-primary/20 to-transparent" />
        )}

        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu className="space-y-1">
              {items.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild>
                    <NavLink
                      to={item.url}
                      end
                      className={`flex items-center rounded-xl py-3 text-muted-foreground hover:text-primary hover:bg-primary/5 transition-all duration-200 ${
                        collapsed ? "justify-center px-0" : "gap-3 px-3"
                      }`}
                      activeClassName="text-primary bg-primary/10 gold-glow-sm"
                    >
                      <item.icon className="w-5 h-5 flex-shrink-0" />
                      {!collapsed && (
                        <span className="font-body text-[15px] font-medium tracking-wide">
                          {item.title}
                        </span>
                      )}
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {/* Bottom decorative element */}
        {!collapsed && (
          <div className="mt-auto pb-6 px-4">
            <div className="h-px bg-gradient-to-r from-transparent via-primary/20 to-transparent mb-4" />
            <p className="text-[11px] text-muted-foreground/50 font-body text-center tracking-wider">
              ✦ From Papers to Perception ✦
            </p>
          </div>
        )}
      </SidebarContent>
    </Sidebar>
  );
};

export default DashboardSidebar;
