APP_NAME=InvoiceApp
BUNDLE_ID=local.invoiceapp
VERSION=1.0
BUILD_DIR=.build/release
BUILD_FILE=BUILD_NUMBER
APP_BUNDLE=dist/$(APP_NAME).app
ICON_SVG=Packaging/AppIcon.svg
ICON_PNG=Packaging/AppIcon.png
ICONSET_DIR=Packaging/AppIcon.iconset
ICON_SOURCE=Packaging/AppIcon.icns

ICON_SIZES=16 32 64 128 256 512

$(ICON_PNG): $(ICON_SVG)
	@echo "Export a 1024x1024 PNG named AppIcon.png from the SVG (manual step if not present)."
	@echo "If you have inkscape or rsvg-convert you can run one of:"
	@echo "  inkscape $(ICON_SVG) --export-type=png --export-filename=$(ICON_PNG) -w 1024 -h 1024" || true
	@echo "  rsvg-convert -w 1024 -h 1024 $(ICON_SVG) -o $(ICON_PNG)" || true
	@false

$(ICON_SOURCE): $(ICON_PNG)
	@echo "Generating .icns from $(ICON_PNG)"
	@rm -rf $(ICONSET_DIR)
	@mkdir -p $(ICONSET_DIR)
	@for sz in $(ICON_SIZES); do \
	  sips -z $$sz $$sz $(ICON_PNG) --out $(ICONSET_DIR)/icon_"$$sz"x"$$sz".png >/dev/null; \
	  S2=$$((sz*2)); \
	  sips -z $$S2 $$S2 $(ICON_PNG) --out $(ICONSET_DIR)/icon_"$$sz"x"$$sz"@2x.png >/dev/null; \
	done
	@iconutil -c icns $(ICONSET_DIR) -o $(ICON_SOURCE)
	@rm -rf $(ICONSET_DIR)
	@echo "Created $(ICON_SOURCE)"

.PHONY: all build app install clean distclean

all: app

build:
	swift build -c release

app: build bump_version $(ICON_SOURCE)
	@echo "Creating app bundle $(APP_BUNDLE)"
	@rm -rf dist/$(APP_NAME).app
	@mkdir -p $(APP_BUNDLE)/Contents/MacOS
	@mkdir -p $(APP_BUNDLE)/Contents/Resources
	@cp Packaging/Info.plist $(APP_BUNDLE)/Contents/Info.plist
	@/usr/libexec/PlistBuddy -c "Set :CFBundleVersion $$(cat $(BUILD_FILE))" $(APP_BUNDLE)/Contents/Info.plist || true
	@cp $(BUILD_DIR)/$(APP_NAME) $(APP_BUNDLE)/Contents/MacOS/$(APP_NAME)
	@if [ -f $(ICON_SOURCE) ]; then cp $(ICON_SOURCE) $(APP_BUNDLE)/Contents/Resources/AppIcon.icns; fi
	@echo "App bundle created at $(APP_BUNDLE)"

install: app
	@mkdir -p ~/Applications
	@cp -R $(APP_BUNDLE) ~/Applications/
	@echo "Installed to ~/Applications/$(APP_NAME).app"

clean:
	swift package clean
	@rm -rf dist
	delocate || true
	rm -rf pkgroot || true
	rm -rf .build
	echo "Cleaned build artifacts"

distclean: clean
	@echo "Distclean complete"

# Increment build number stored in BUILD_NUMBER and stage for later commit.
.PHONY: bump_version
bump_version:
	@if [ ! -f $(BUILD_FILE) ]; then echo 1 > $(BUILD_FILE); fi
	@old=$$(cat $(BUILD_FILE)); new=$$((old + 1)); echo $$new > $(BUILD_FILE); echo "Incremented build number: $$old -> $$new";
