import { create } from "zustand";

interface JobState {
  selectedJobId: string | null;
  setSelectedJobId: (id: string | null) => void;
}

export const useJobStore = create<JobState>((set) => ({
  selectedJobId: localStorage.getItem("rv_selected_job"),
  setSelectedJobId: (id) => {
    if (id) localStorage.setItem("rv_selected_job", id);
    else localStorage.removeItem("rv_selected_job");
    set({ selectedJobId: id });
  },
}));
