import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/src/api/client";
import { useAuth } from "@/src/contexts/AuthContext";

export interface Company {
  company_id: string;
  name: string;
  industry: string;
  logo_color: string;
}

interface CompanyCtx {
  companies: Company[];
  active: Company | null;
  loading: boolean;
  refresh: () => Promise<void>;
  switchTo: (id: string) => Promise<void>;
}

const Ctx = createContext<CompanyCtx>({
  companies: [],
  active: null,
  loading: false,
  refresh: async () => undefined,
  switchTo: async () => undefined,
});

export function useCompanies() {
  return useContext(Ctx);
}

export function CompanyProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!user) {
      setCompanies([]);
      setActiveId(null);
      return;
    }
    setLoading(true);
    try {
      const r = await apiFetch<{ companies: Company[]; active_company_id: string }>("/companies");
      setCompanies(r.companies);
      setActiveId(r.active_company_id);
    } finally {
      setLoading(false);
    }
  }, [user]);

  const switchTo = useCallback(async (id: string) => {
    await apiFetch("/companies/switch", {
      method: "POST",
      body: JSON.stringify({ company_id: id }),
    });
    setActiveId(id);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const active = useMemo(
    () => companies.find((c) => c.company_id === activeId) ?? null,
    [companies, activeId],
  );

  return (
    <Ctx.Provider value={{ companies, active, loading, refresh, switchTo }}>
      {children}
    </Ctx.Provider>
  );
}
