@echo off
echo Building Rust LCA Backend...
echo.

cd african_lca_backend

echo Checking Rust installation...
cargo --version
echo.

echo Building in debug mode...
cargo build

echo.
echo Building in release mode (optimized)...
cargo build --release

echo.
echo Build complete!
echo Debug binary: target\debug\server.exe  
echo Release binary: target\release\server.exe
echo.

pause