# Scripts Directory

> **Updated**: 2026-02-24
> **Version**: v3.1.1

---

## 📁 Directory Structure

```
scripts/
├── startup/              # Startup scripts (启动脚本)
│   ├── quickstart.bat    # Windows launcher (统一入口)
│   ├── quickstart-cmd.bat # Windows batch launcher
│   ├── quickstart.sh     # Linux/macOS shell launcher
│   └── quickstart.js     # Cross-platform Node.js launcher
│
├── build/                # Build scripts (打包脚本)
│   ├── build.bat         # Windows Electron app build script
│   └── build.sh          # Linux/macOS Electron app build script
│
└── fix/                  # Fix tools (修复工具)
    ├── fix-electron.bat  # Electron fix (Windows)
    ├── fix-electron.sh   # Electron fix (Linux/macOS)
    └── diagnose-electron.bat  # Electron diagnostics
```

---

## 🚀 Startup Scripts

### Quick Start (Recommended)

**Windows**:
```bash
# Double-click or run from command line
start.bat
```

**Linux/macOS**:
```bash
# Add execute permission and run
chmod +x start.sh
./start.sh
```

### Advanced Usage

**Windows Batch**:
```bash
scripts/startup/quickstart-cmd.bat
```

**Linux/macOS Shell**:
```bash
bash scripts/startup/quickstart.sh
```

**Node.js (Cross-platform)**:
```bash
node scripts/startup/quickstart.js
```

---

## 🔨 Build Scripts

### Build Electron App

The build scripts package the frontend Electron application into distributable installers.

**Windows**:
```bash
scripts/build/build.bat
```

**Linux/macOS**:
```bash
chmod +x scripts/build/build.sh
./scripts/build/build.sh
```

### Build Options

The build script will prompt you to select target platform:
- [1] Windows (NSIS installer + Portable)
- [2] Linux (AppImage + deb + rpm)
- [3] macOS (DMG + ZIP)
- [4] All platforms

### Output

Built files are saved to: `frontend/dist/` directory.

**Windows**:
- `AutoGeo-{version}-windows-x64.exe` (NSIS installer)
- `AutoGeo-{version}-windows-x64.exe` (Portable)

**Linux**:
- `AutoGeo-{version}-linux-x64.AppImage` (Universal Linux package)
- `AutoGeo-{version}-linux-x64.deb` (Debian/Ubuntu)
- `AutoGeo-{version}-linux-x64.rpm` (Fedora/RHEL)

**macOS**:
- `AutoGeo-{version}-macos.dmg` (DMG installer)
- `AutoGeo-{version}-mac.zip` (ZIP archive)

---

## 🔧 Fix Tools

### Electron Fix

Automatically fix Electron installation issues (missing path.txt).

**Windows**:
```bash
scripts/fix/fix-electron.bat
```

**Linux/macOS**:
```bash
chmod +x scripts/fix/fix-electron.sh
./scripts/fix/fix-electron.sh
```

### Electron Diagnostics

Diagnose Electron startup problems.

**Windows only**:
```bash
scripts/fix/diagnose-electron.bat
```

---

## 📝 Script Guidelines

### Adding New Scripts

1. **Choose the right category**:
   - `startup/` - Launchers and startup related
   - `build/` - Build and packaging scripts
   - `fix/` - Repair and diagnostic tools

2. **Use English names**:
   - Use descriptive English filenames
   - Add comments in English (or Chinese with English comments)

3. **Cross-platform support**:
   - Provide both `.bat` (Windows) and `.sh` (Linux/macOS) versions
   - Or use `.js` for true cross-platform

4. **Documentation**:
   - Add header comments with purpose, maintainer, version
   - Include usage examples in comments

### Script Template

```batch
@echo off
REM ========================================
REM Script Name
REM Description
REM Maintainer: Your Name
REM Version: v1.0.0
REM Updated: YYYY-MM-DD
REM ========================================
REM
REM Purpose: What this script does
REM Usage: How to use this script
REM

REM Your code here
```

---

## 🔍 Troubleshooting

### Build fails

**Problem**: electron-builder errors
**Solution**:
```bash
# Clean and reinstall
cd frontend
rm -rf node_modules
rm package-lock.json
npm install
```

### Electron issues

**Problem**: Electron won't start
**Solution**:
```bash
# Windows
scripts/fix/fix-electron.bat

# Linux/macOS
scripts/fix/fix-electron.sh
```

### Startup script not found

**Problem**: "Command not found" error
**Solution**:
- Make sure you're in the project root directory
- Check the file path: `ls scripts/startup/`

---

## 📞 Support

For issues or questions:
- Check the main [README.md](../README.md)
- See [docs/](../docs/) for detailed documentation
- Open an issue on GitHub

---

## 🚀 后端部署脚本 (新增)

### 快速开始

```bash
# 1. 配置环境变量
cp .env.prod.example .env
vim .env  # 填入真实配置

# 2. 首次部署
./scripts/deploy.sh

# 3. 后续更新
./scripts/update.sh

# 4. 数据库备份
./scripts/backup.sh
```

### 部署脚本说明

| 脚本 | 用途 | 用法 |
|------|------|------|
| `deploy.sh` | 首次部署或完整重新部署 | `./scripts/deploy.sh [env文件]` |
| `update.sh` | 更新到最新镜像（零停机） | `./scripts/update.sh` |
| `backup.sh` | 数据库备份 | `./scripts/backup.sh` |

### 故障排查

```bash
# 查看服务状态
docker-compose -f docker-compose.prod.yml ps

# 查看日志
docker-compose -f docker-compose.prod.yml logs -f backend

# 重启服务
docker-compose -f docker-compose.prod.yml restart
```

---

**Updated**: 2026-05-08
**Version**: v3.2.0
