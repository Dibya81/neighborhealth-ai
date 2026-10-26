# Files to move into place (one-time)

These couldn't be written into their final location remotely. From the repo root, run:

```bash
cp infra/nh.mk Makefile
mkdir -p .github/workflows && cp infra/github-workflows/*.yml .github/workflows/
```

Until you do, you can still use the Makefile directly: `make -f infra/nh.mk <target>`.
