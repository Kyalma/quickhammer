import { createTheme } from "@mui/material/styles";

/**
 * MUI's stock dark palette leads the look — there is no custom brand colour.
 *
 * The only overrides are the 44px touch-target floors. QuickHammer is used on
 * phones and iPads beside a table, and MUI's default medium controls sit around
 * 36px; the plain CSS this replaced set `min-height: 44px` on every control for
 * that reason. `outlined` is the default Button variant because every button in
 * this app previously had a visible border, and MUI's default (`text`) reads as
 * disabled next to the filled primary actions.
 */
export const theme = createTheme({
  palette: { mode: "dark" },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        "#root": { minHeight: "100dvh", display: "flex", flexDirection: "column" },
      },
    },
    MuiButton: {
      defaultProps: { variant: "outlined" },
      styleOverrides: { root: { minHeight: 44 } },
    },
    MuiOutlinedInput: { styleOverrides: { root: { minHeight: 44 } } },
    MuiMenuItem: { styleOverrides: { root: { minHeight: 44 } } },
    MuiFormControlLabel: { styleOverrides: { root: { minHeight: 44 } } },
  },
});
