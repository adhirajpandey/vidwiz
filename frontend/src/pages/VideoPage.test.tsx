// @vitest-environment jsdom
import { act, cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import VideoPage from "./VideoPage";
import { notesApi } from "../api";

vi.mock("../api", () => ({
  videosApi: {
    getVideo: vi
      .fn()
      .mockResolvedValue({
        video_id: "abc123DEF45",
        title: "Example",
        metadata: null,
      }),
  },
  notesApi: { listNotes: vi.fn() },
  authApi: { getMe: vi.fn().mockResolvedValue({ ai_notes_enabled: false }) },
}));
vi.mock("../lib/authUtils", () => ({ getToken: () => "fixture" }));
vi.mock("../components/Seo", () => ({ default: () => null }));
const { addToast } = vi.hoisted(() => ({ addToast: vi.fn() }));
vi.mock("../hooks/useToast", () => ({ useToast: () => ({ addToast }) }));
function Navigation() {
  const navigate = useNavigate();
  return (
    <>
      <button onClick={() => navigate("#note-8")}>Other note</button>
      <button onClick={() => navigate(-1)}>Back</button>
    </>
  );
}
const notes = [7, 8].map((id) => ({
  id,
  video_id: "abc123DEF45",
  user_id: 1,
  timestamp: `0:0${id}`,
  text: `Note ${id}`,
  generated_by_ai: false,
  created_at: "",
  updated_at: "",
}));
function setup() {
  render(
    <MemoryRouter initialEntries={["/dashboard/abc123DEF45#note-7"]}>
      <Routes>
        <Route
          path="/dashboard/:videoId"
          element={
            <>
              <VideoPage />
              <Navigation />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}
beforeEach(() => {
  vi.mocked(notesApi.listNotes).mockReset();
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(cleanup);
it("waits for notes before focusing the linked note and supports Back", async () => {
  let resolve!: (value: typeof notes) => void;
  vi.mocked(notesApi.listNotes).mockReturnValue(
    new Promise((done) => {
      resolve = done;
    }),
  );
  setup();
  expect(screen.queryByText(/no longer available/)).toBeNull();
  await act(async () => resolve(notes));
  expect(document.activeElement?.id).toBe("note-7");
  expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
  const user = userEvent.setup();
  await user.click(screen.getByText("Other note"));
  expect(document.activeElement?.id).toBe("note-8");
  await user.click(screen.getByText("Back"));
  expect(document.activeElement?.id).toBe("note-7");
});
it("shows a missing-note message without leaving the video", async () => {
  vi.mocked(notesApi.listNotes).mockResolvedValue([]);
  setup();
  await screen.findByText(/This note is no longer available/);
  expect(screen.getByRole("heading", { name: "Example" })).toBeTruthy();
});
