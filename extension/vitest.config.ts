export default {
  test: {
    environment: "jsdom",
    environmentOptions: { jsdom: { url: "https://dethitiengnhat.com/" } },
    include: ["tests/**/*.test.ts"],
    restoreMocks: true,
  },
};
