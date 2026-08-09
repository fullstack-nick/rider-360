# Rider 360 dataLayer Lab

This self-contained page demonstrates the versioned SizePath and ecommerce tracking contract.
It never loads a tag manager or sends a network beacon. Open it through a local static server:

```powershell
python -m http.server 8088 --directory demo/data-layer
```

Then visit <http://localhost:8088>. The guided flow writes only validated fictional payloads to
`window.dataLayer`. The “Test the PII guard” control proves that a payload containing a forbidden
personal-detail field is rejected before it reaches the layer.

Run the non-browser contract check with `node scripts/validate_demo.mjs`.
