// @vitest-environment jsdom
import { act, cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter, useLocation, useNavigate } from "react-router-dom";
import DashboardPage from "./DashboardPage";
import { notesApi, videosApi } from "../api";

vi.mock("../api", () => ({
  videosApi: { listVideos: vi.fn(), librarySummary: vi.fn() },
  notesApi: { search: vi.fn() },
}));
vi.mock("../components/Seo", () => ({ default: () => null }));
const video = {
  video_id: "abc123DEF45",
  title: "A matching title",
  metadata: null,
  note_count: 2,
  last_activity_at: null,
};
const result = {
  videos: [video],
  total: 12,
  page: 1,
  per_page: 10,
  total_pages: 2,
};
function Location() {
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <>
      <output data-testid="url">{location.search}</output>
      <button onClick={() => navigate(-1)}>Back</button>
    </>
  );
}
function setup(url = "/dashboard") {
  render(
    <MemoryRouter initialEntries={[url]}>
      <DashboardPage />
      <Location />
    </MemoryRouter>,
  );
  return userEvent.setup();
}
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(videosApi.librarySummary).mockResolvedValue({
    videos: 12,
    notes: 20,
    ai_notes: 3,
    wiz_chats: 4,
    recent_videos: [video],
  });
  vi.mocked(videosApi.listVideos).mockResolvedValue(result);
  vi.mocked(notesApi.search).mockResolvedValue({
    notes: [
      {
        id: 7,
        video_id: video.video_id,
        title: video.title,
        metadata: null,
        timestamp: "01:20",
        generated_by_ai: true,
        excerpt: "A matching note <script>",
      },
    ],
    total: 11,
    page: 1,
    per_page: 10,
    total_pages: 2,
  });
});
afterEach(cleanup);
it("separates search results, escapes excerpts, and paginates independently", async () => {
  const user = setup();
  await screen.findByText("Continue exploring");
  await user.type(
    screen.getByRole("textbox", { name: "Search videos and notes" }),
    "matching",
  );
  await user.click(screen.getByRole("button", { name: "Search" }));
  await screen.findByRole("heading", { name: "Videos (12)" });
  expect(screen.queryByText("Continue exploring")).toBeNull();
  expect(screen.getByRole("heading", { name: "Notes (11)" })).toBeTruthy();
  expect(
    screen.getByRole("link", { name: "Open note" }).getAttribute("href"),
  ).toBe("/dashboard/abc123DEF45#note-7");
  expect(screen.getByText(/note <script>/)).toBeTruthy();
  expect(document.querySelector("script")).toBeNull();
  await user.click(
    within(
      screen.getByRole("navigation", { name: "Notes pagination" }),
    ).getByText("Next"),
  );
  expect(notesApi.search).toHaveBeenLastCalledWith("matching", 2);
  expect(videosApi.listVideos).toHaveBeenCalledTimes(2);
  expect(screen.getByTestId("url").textContent).toContain("notesPage=2");
  await user.click(screen.getByText("Back"));
  expect(notesApi.search).toHaveBeenLastCalledWith("matching", 1);
  await user.click(screen.getByRole("button", { name: "Clear" }));
  await screen.findByText("Continue exploring");
});
it("validates short queries and restores search from the URL", async () => {
  const user = setup("/dashboard?q=matching&videosPage=2");
  await screen.findByRole("heading", { name: "Videos (12)" });
  expect(videosApi.listVideos).toHaveBeenLastCalledWith(
    expect.objectContaining({ q: "matching", page: 2 }),
  );
  const input = screen.getByRole("textbox", {
    name: "Search videos and notes",
  });
  await user.clear(input);
  await user.type(input, "a");
  await user.click(screen.getByRole("button", { name: "Search" }));
  expect(screen.getByRole("alert").textContent).toContain("at least two");
});
it("ignores a late response from an older query", async () => {
  let resolveOld!: (value: typeof result) => void;
  vi.mocked(videosApi.listVideos).mockReturnValueOnce(
    new Promise((resolve) => {
      resolveOld = resolve;
    }),
  );
  const user = setup("/dashboard?q=old");
  const input = screen.getByRole("textbox", {
    name: "Search videos and notes",
  });
  await user.clear(input);
  await user.type(input, "new");
  await user.click(screen.getByRole("button", { name: "Search" }));
  await screen.findByRole("heading", { name: "Videos (12)" });
  await act(async () => resolveOld({ ...result, total: 99 }));
  expect(screen.queryByRole("heading", { name: "Videos (99)" })).toBeNull();
});
it("keeps note results when video loading fails and retries only videos", async () => {
  vi.mocked(videosApi.listVideos).mockRejectedValueOnce(new Error("offline"));
  const user = setup("/dashboard?q=matching");
  await screen.findByText("Unable to load this section");
  expect(screen.getByRole("link", { name: "Open note" })).toBeTruthy();
  await user.click(screen.getByRole("button", { name: /try again/i }));
  await screen.findByRole("heading", { name: "Videos (12)" });
  expect(notesApi.search).toHaveBeenCalledTimes(1);
});
