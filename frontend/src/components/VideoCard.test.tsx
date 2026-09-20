// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import VideoCard from "./VideoCard";
import type { VideoMetadata } from "../api/types";

afterEach(cleanup);
function show(metadata: VideoMetadata | null, featured = false) {
  return render(<MemoryRouter><VideoCard featured={featured} video={{
    video_id: "abc123DEF45", title: "A video", note_count: 1,
    last_activity_at: new Date().toISOString(), metadata,
  }} /></MemoryRouter>);
}

it.each([false, true])("shows metadata and preserves destinations, featured=%s", (featured) => {
  show({ view_count: 123000, upload_date: "20260912", duration: 3661 }, featured);
  expect(screen.getByText("123K views")).toBeTruthy();
  expect(screen.getByText("Uploaded 12 Sept 2026")).toBeTruthy();
  expect(screen.getByText("1:01:01")).toBeTruthy();
  if (!featured) {
    expect(screen.getByText("1 note")).toBeTruthy();
    expect(screen.getByText("Active today")).toBeTruthy();
  }
  expect(screen.getByRole("link", { name: "Ask Wiz" }).getAttribute("href")).toBe("/wiz/abc123DEF45");
  expect(screen.getByRole("link", { name: "View notes" }).getAttribute("href")).toBe("/dashboard/abc123DEF45");
  expect(screen.getByRole("link", { name: "Watch A video on YouTube" }).getAttribute("href")).toBe("https://www.youtube.com/watch?v=abc123DEF45");
});

it("keeps zero views and prefers the supplied duration label", () => {
  show({ view_count: 0, upload_date: "20260230", duration: 61, duration_string: "2:03" });
  expect(screen.getByText("0 views")).toBeTruthy();
  expect(screen.getByText("2:03")).toBeTruthy();
  expect(screen.queryByText(/Uploaded/)).toBeNull();
});

it.each([null, { view_count: -1, upload_date: "invalid", duration: -1 },
  { view_count: NaN, upload_date: "20261301", duration: Infinity }])("omits invalid metadata %j", (metadata) => {
  const { container } = show(metadata);
  expect(container.querySelector(".library-video-details")).toBeNull();
  expect(container.querySelector(".library-thumbnail > span")).toBeNull();
});

it("formats minute durations and retains the link after an image fails", () => {
  const { container } = show({ duration: 65 });
  expect(screen.getByText("1:05")).toBeTruthy();
  fireEvent.error(container.querySelector("img")!);
  expect(container.querySelector("img")).toBeNull();
  expect(screen.getByRole("link", { name: "Watch A video on YouTube" })).toBeTruthy();
});
