// Generates app/src/main/res/values/strings.xml and values-gu/strings.xml from one table.
// Usage (from android/): node tools/genstrings.js app/src/main/res
const fs = require('fs');
const path = require('path');
const res = process.argv[2];

// [name, english, gujarati]
const S = [
  ['nav_home', 'Home', 'હોમ'],
  ['nav_map', 'Map', 'નકશો'],
  ['nav_downloads', 'Downloads', 'ડાઉનલોડ'],
  ['nav_settings', 'Settings', 'સેટિંગ્સ'],
  ['action_back', 'Back', 'પાછા'],
  ['action_search', 'Search', 'શોધો'],
  ['action_clear', 'Clear', 'સાફ કરો'],
  ['action_retry', 'Retry', 'ફરી પ્રયાસ કરો'],
  ['action_open_browser', 'Open in browser', 'બ્રાઉઝરમાં ખોલો'],
  ['action_share', 'Share', 'શેર કરો'],
  ['action_download', 'Download', 'ડાઉનલોડ કરો'],
  ['action_update', 'Update', 'અપડેટ કરો'],
  ['action_delete', 'Delete', 'કાઢી નાખો'],
  ['action_open', 'Open', 'ખોલો'],
  ['action_ok', 'OK', 'બરાબર'],
  ['action_accept', 'I understand', 'હું સમજું છું'],
  ['search_hint', 'Scheme number or area', 'સ્કીમ નંબર અથવા વિસ્તાર'],
  ['search_results', 'Search results', 'શોધ પરિણામો'],
  ['last_updated', 'Last updated: %1$s', 'છેલ્લે અપડેટ: %1$s'],
  ['last_updated_never', 'Catalog not updated yet', 'કેટલોગ હજી અપડેટ થયું નથી'],
  ['last_checked', 'Last checked: %1$s', 'છેલ્લે તપાસ્યું: %1$s'],
  ['home_cities', 'Cities', 'શહેરો'],
  ['home_recent', 'Recently viewed', 'તાજેતરમાં જોયેલ'],
  ['home_tools', 'Tools', 'સાધનો'],
  ['home_empty', 'No schemes in the catalog yet. They will appear after the next catalog update.', 'કેટલોગમાં હજી કોઈ સ્કીમ નથી. આગામી કેટલોગ અપડેટ પછી તે દેખાશે.'],
  ['whats_new_title', "What's new", 'નવું શું છે'],
  ['whats_new_empty', 'No recent changes recorded.', 'તાજેતરના કોઈ ફેરફાર નોંધાયા નથી.'],
  ['change_new', 'New schemes', 'નવી સ્કીમ'],
  ['change_changed', 'Updated', 'અપડેટ થયેલ'],
  ['change_removed', 'Removed from the official website', 'સત્તાવાર વેબસાઇટ પરથી દૂર કરાયેલ'],
  ['what_map_file', 'map updated', 'નકશો અપડેટ થયો'],
  ['what_other_file', 'document updated', 'દસ્તાવેજ અપડેટ થયો'],
  ['what_status', 'status changed', 'સ્થિતિ બદલાઈ'],
  ['what_name', 'name changed', 'નામ બદલાયું'],
  ['what_new_file', 'new document', 'નવો દસ્તાવેજ'],
  ['badge_new', 'New', 'નવું'],
  ['badge_updated', 'Updated', 'અપડેટ'],
  ['badge_removed', 'Removed', 'દૂર કરેલ'],
  ['status_draft', 'Draft', 'ડ્રાફ્ટ'],
  ['status_preliminary', 'Preliminary', 'પ્રાથમિક'],
  ['status_final', 'Final', 'અંતિમ'],
  ['status_sanctioned_variation', 'Sanctioned variation', 'મંજૂર ફેરફાર'],
  ['status_unknown', 'Status unknown', 'સ્થિતિ અજ્ઞાત'],
  ['filter_all', 'All statuses', 'બધી સ્થિતિ'],
  ['filter_all_types', 'All types', 'બધા પ્રકાર'],
  ['sort_number', 'By number', 'નંબર મુજબ'],
  ['sort_date', 'By date', 'તારીખ મુજબ'],
  ['list_empty', 'No schemes match.', 'કોઈ સ્કીમ મળી નથી.'],
  ['detail_authority', 'Authority', 'સત્તામંડળ'],
  ['detail_status', 'Status', 'સ્થિતિ'],
  ['detail_status_source', 'Status on official website', 'સત્તાવાર વેબસાઇટ પર સ્થિતિ'],
  ['detail_status_date', 'Status date', 'સ્થિતિ તારીખ'],
  ['detail_city', 'City', 'શહેર'],
  ['detail_name_en', 'Name (English)', 'નામ (અંગ્રેજી)'],
  ['detail_name_gu', 'Name (Gujarati)', 'નામ (ગુજરાતી)'],
  ['detail_first_seen', 'In catalog since', 'કેટલોગમાં ત્યારથી'],
  ['detail_map_updated', 'Map updated on %1$s', 'નકશો %1$s ના રોજ અપડેટ થયો'],
  ['detail_removed', 'This scheme is no longer listed on the official website. The last known information is shown.', 'આ સ્કીમ હવે સત્તાવાર વેબસાઇટ પર દર્શાવેલ નથી. છેલ્લી જાણીતી માહિતી બતાવવામાં આવી છે.'],
  ['detail_files', 'Documents', 'દસ્તાવેજો'],
  ['detail_older_files', 'Older versions', 'જૂના સંસ્કરણો'],
  ['detail_open_source', 'Open official source', 'સત્તાવાર સ્રોત ખોલો'],
  ['detail_view_on_map', 'View on map', 'નકશા પર જુઓ'],
  ['detail_report', 'Report a wrong or outdated map', 'ખોટો અથવા જૂનો નકશો જણાવો'],
  ['detail_not_found', 'Scheme not found.', 'સ્કીમ મળી નથી.'],
  ['disclaimer_short', 'Maps are for reference only and are not legal documents. Always verify with the concerned authority.', 'નકશા ફક્ત સંદર્ભ માટે છે અને કાનૂની દસ્તાવેજ નથી. હંમેશા સંબંધિત સત્તામંડળ પાસે ચકાસણી કરો.'],
  ['file_kind_map', 'Map', 'નકશો'],
  ['file_kind_scheme_book', 'Scheme book', 'સ્કીમ બુક'],
  ['file_kind_notification', 'Notification', 'જાહેરનામું'],
  ['file_kind_redistribution_statement', 'Redistribution statement', 'પુનઃવિતરણ પત્રક'],
  ['file_kind_other', 'Document', 'દસ્તાવેજ'],
  ['file_downloaded', 'Downloaded', 'ડાઉનલોડ થયેલ'],
  ['file_update_available', 'Newer version available', 'નવું સંસ્કરણ ઉપલબ્ધ'],
  ['download_progress', 'Downloading… %1$d%%', 'ડાઉનલોડ થઈ રહ્યું છે… %1$d%%'],
  ['download_progress_unknown', 'Downloading…', 'ડાઉનલોડ થઈ રહ્યું છે…'],
  ['download_failed', 'Download failed: %1$s', 'ડાઉનલોડ નિષ્ફળ: %1$s'],
  ['viewer_error_title', 'Could not open the map', 'નકશો ખોલી શકાયો નહીં'],
  ['viewer_error_body', 'The government website may be down or slow. Try again, or open the file in your browser.', 'સરકારી વેબસાઇટ બંધ અથવા ધીમી હોઈ શકે છે. ફરી પ્રયાસ કરો, અથવા ફાઇલ બ્રાઉઝરમાં ખોલો.'],
  ['viewer_page', 'Page %1$d of %2$d', 'પાનું %1$d / %2$d'],
  ['viewer_prev_page', 'Previous page', 'પાછલું પાનું'],
  ['viewer_next_page', 'Next page', 'આગળનું પાનું'],
  ['viewer_invalid', 'This file could not be displayed. Try opening it in your browser.', 'આ ફાઇલ બતાવી શકાઈ નહીં. તેને બ્રાઉઝરમાં ખોલવાનો પ્રયાસ કરો.'],
  ['share_pdf_title', 'Share map', 'નકશો શેર કરો'],
  ['share_scheme_text', '%1$s\nOfficial source: %2$s\n(Shared from OpenNaksha. Maps are for reference only.)', '%1$s\nસત્તાવાર સ્રોત: %2$s\n(OpenNaksha પરથી શેર કરેલ. નકશા ફક્ત સંદર્ભ માટે છે.)'],
  ['map_my_location', 'My location', 'મારું સ્થાન'],
  ['map_opacity', 'Overlay opacity', 'ઓવરલે અપારદર્શકતા'],
  ['map_approximate', 'Approximate position', 'અંદાજિત સ્થાન'],
  ['map_outdated', "This scheme's map was updated. This overlay may be outdated — check the latest PDF.", 'આ સ્કીમનો નકશો અપડેટ થયો છે. આ ઓવરલે જૂનો હોઈ શકે છે — નવીનતમ PDF તપાસો.'],
  ['map_no_overlays', 'No schemes on the map yet. Overlays are added as schemes are georeferenced.', 'નકશા પર હજી કોઈ સ્કીમ નથી. સ્કીમ જીઓરેફરન્સ થતાં ઓવરલે ઉમેરાશે.'],
  ['map_open_scheme', 'Open scheme', 'સ્કીમ ખોલો'],
  ['map_overlay_error', 'Could not load the overlay image. Check your connection.', 'ઓવરલે છબી લોડ થઈ શકી નહીં. તમારું કનેક્શન તપાસો.'],
  ['map_location_denied', 'Location permission was not granted.', 'સ્થાનની પરવાનગી આપવામાં આવી નથી.'],
  ['map_close', 'Close', 'બંધ કરો'],
  ['downloads_empty', 'No downloaded maps. Download a map from a scheme page to view it offline.', 'કોઈ ડાઉનલોડ કરેલ નકશો નથી. ઑફલાઇન જોવા માટે સ્કીમ પેજ પરથી નકશો ડાઉનલોડ કરો.'],
  ['downloads_storage', 'Storage used: %1$s', 'વપરાયેલ સંગ્રહ: %1$s'],
  ['settings_language', 'Language', 'ભાષા'],
  ['settings_language_system', 'System default', 'સિસ્ટમ ડિફોલ્ટ'],
  ['settings_updates', 'Catalog updates', 'કેટલોગ અપડેટ્સ'],
  ['settings_check_now', 'Check for updates now', 'હવે અપડેટ તપાસો'],
  ['settings_checking', 'Checking…', 'તપાસી રહ્યા છીએ…'],
  ['settings_auto_check', 'Check automatically every day', 'દરરોજ આપમેળે તપાસો'],
  ['settings_wifi_only', 'Only on Wi-Fi', 'ફક્ત Wi-Fi પર'],
  ['settings_clear_cache', 'Clear cache', 'કેશ સાફ કરો'],
  ['settings_clear_cache_desc', 'Removes cached overlays and web data. Downloaded maps are kept.', 'કેશ કરેલ ઓવરલે અને વેબ ડેટા દૂર કરે છે. ડાઉનલોડ કરેલ નકશા રહેશે.'],
  ['settings_cache_cleared', 'Cache cleared', 'કેશ સાફ થઈ'],
  ['settings_about', 'About', 'વિશે'],
  ['settings_version', 'OpenNaksha %1$s', 'OpenNaksha %1$s'],
  ['settings_about_text', 'A free, open-source app with no ads, no tracking and no login. Scheme lists are collected weekly from public government websites; maps are downloaded directly from the official links.', 'જાહેરાત, ટ્રેકિંગ અને લોગિન વિનાની મફત, ઓપન-સોર્સ એપ. સ્કીમની યાદી દર અઠવાડિયે જાહેર સરકારી વેબસાઇટ્સ પરથી એકત્ર થાય છે; નકશા સીધા સત્તાવાર લિંક પરથી ડાઉનલોડ થાય છે.'],
  ['settings_licenses', 'Open-source licenses', 'ઓપન-સોર્સ લાઇસન્સ'],
  ['settings_not_configured', 'Online catalog updates are not configured in this build.', 'આ બિલ્ડમાં ઓનલાઇન કેટલોગ અપડેટ ગોઠવેલ નથી.'],
  ['update_result_updated', 'Catalog updated', 'કેટલોગ અપડેટ થયું'],
  ['update_result_current', 'Catalog is up to date', 'કેટલોગ અદ્યતન છે'],
  ['update_result_failed', 'Could not check for updates. Your current data is kept.', 'અપડેટ તપાસી શકાયા નહીં. તમારો હાલનો ડેટા યથાવત છે.'],
  ['new_version_available', 'A new app version (%1$s) is available.', 'નવું એપ સંસ્કરણ (%1$s) ઉપલબ્ધ છે.'],
  ['new_version_download', 'Download', 'ડાઉનલોડ'],
  ['tools_converter', 'Land unit converter', 'જમીન માપ રૂપાંતર'],
  ['tools_anyror', 'AnyROR land records', 'AnyROR જમીન રેકર્ડ'],
  ['tools_anyror_desc', 'Official Gujarat land record portal (opens in browser)', 'ગુજરાતનું સત્તાવાર જમીન રેકર્ડ પોર્ટલ (બ્રાઉઝરમાં ખુલશે)'],
  ['converter_value', 'Area', 'ક્ષેત્રફળ'],
  ['converter_from', 'Unit', 'એકમ'],
  ['converter_note', 'Values used: 1 vaar = 1 sq yard = 0.8361 m²; 1 guntha = 121 sq yards = 101.17 m²; 1 vigha = 16 guntha = 17,424 sq ft = 1,618.74 m²; 1 acre = 40 guntha = 4,046.86 m²; 1 hectare = 10,000 m². The size of a vigha (bigha) varies by region in Gujarat — confirm the local value before relying on it.', 'વપરાયેલ મૂલ્યો: 1 વાર = 1 ચો. યાર્ડ = 0.8361 m²; 1 ગુંઠા = 121 ચો. વાર = 101.17 m²; 1 વીઘા = 16 ગુંઠા = 17,424 ચો. ફૂટ = 1,618.74 m²; 1 એકર = 40 ગુંઠા = 4,046.86 m²; 1 હેક્ટર = 10,000 m². ગુજરાતમાં વીઘાનું માપ પ્રદેશ પ્રમાણે બદલાય છે — ઉપયોગ કરતા પહેલાં સ્થાનિક મૂલ્ય ચકાસો.'],
  ['unit_sq_m', 'Square metre (m²)', 'ચોરસ મીટર (m²)'],
  ['unit_sq_ft', 'Square foot (sq ft)', 'ચોરસ ફૂટ'],
  ['unit_sq_yard', 'Square yard (vaar)', 'ચોરસ વાર'],
  ['unit_guntha', 'Guntha', 'ગુંઠા'],
  ['unit_vigha', 'Vigha / bigha (varies by region)', 'વીઘા (પ્રદેશ પ્રમાણે બદલાય)'],
  ['unit_acre', 'Acre', 'એકર'],
  ['unit_hectare', 'Hectare', 'હેક્ટર'],
  ['licenses_intro', 'OpenNaksha is MIT-licensed and uses these open-source components:', 'OpenNaksha MIT લાઇસન્સ હેઠળ છે અને આ ઓપન-સોર્સ ઘટકોનો ઉપયોગ કરે છે:'],
  ['licenses_osm_notice', 'Map data © OpenStreetMap contributors (ODbL). Basemap by OpenFreeMap.', 'નકશા ડેટા © OpenStreetMap યોગદાનકર્તાઓ (ODbL). બેઝમેપ OpenFreeMap દ્વારા.'],
  ['report_subject', 'OpenNaksha: wrong or outdated map — %1$s', 'OpenNaksha: ખોટો અથવા જૂનો નકશો — %1$s'],
  ['report_body', 'Scheme: %1$s\nSource page: %2$s\n\nWhat is wrong:\n', 'સ્કીમ: %1$s\nસ્રોત પેજ: %2$s\n\nશું ખોટું છે:\n'],
  ['error_no_app', 'No app found to open this.', 'આ ખોલવા માટે કોઈ એપ મળી નથી.'],
  ['disclaimer_title', 'Disclaimer', 'અસ્વીકરણ'],
  ['disclaimer_text', 'OpenNaksha is an independent app and is not affiliated with or endorsed by any government entity. Maps come from publicly available government websites, linked with each map. Maps are for reference only and are not legal documents. Map overlays are approximate and may be outdated. Always verify with the concerned authority.', 'OpenNaksha એક સ્વતંત્ર એપ છે અને કોઈ પણ સરકારી સંસ્થા સાથે સંકળાયેલ નથી કે તેના દ્વારા માન્ય નથી. નકશા જાહેરમાં ઉપલબ્ધ સરકારી વેબસાઇટ્સ પરથી લેવામાં આવ્યા છે, અને દરેક નકશા સાથે તેની લિંક આપેલ છે. નકશા ફક્ત સંદર્ભ માટે છે અને કાનૂની દસ્તાવેજ નથી. નકશા ઓવરલે અંદાજિત છે અને જૂના હોઈ શકે છે. હંમેશા સંબંધિત સત્તામંડળ પાસે ચકાસણી કરો.'],
];

// [name, {one, other} en, {one, other} gu]
const P = [
  ['city_scheme_count', { one: '%d scheme', other: '%d schemes' }, { one: '%d સ્કીમ', other: '%d સ્કીમ' }],
  ['news_new', { one: '%1$d new scheme in %2$s', other: '%1$d new schemes in %2$s' }, { one: '%2$s માં %1$d નવી સ્કીમ', other: '%2$s માં %1$d નવી સ્કીમ' }],
  ['news_updated', { one: '%1$d scheme updated in %2$s', other: '%1$d schemes updated in %2$s' }, { one: '%2$s માં %1$d સ્કીમ અપડેટ થઈ', other: '%2$s માં %1$d સ્કીમ અપડેટ થઈ' }],
];

// Not translated (names, config).
const FIXED = [
  ['app_name', 'OpenNaksha'],
  ['scheme_title', '%1$s %2$s'],
  ['settings_language_en', 'English'],
  ['settings_language_gu', 'ગુજરાતી'],
  // Set one of these to enable "Report a wrong/outdated map" (email wins). Empty = button hidden.
  ['report_email', ''],
  ['report_issues_url', ''],
];

const LICENSES = [
  'Kotlin, kotlinx.coroutines, kotlinx.serialization|Apache License 2.0',
  'AndroidX (Compose, Material 3, Room, WorkManager, DataStore, Navigation, Lifecycle)|Apache License 2.0',
  'Dagger / Hilt|Apache License 2.0',
  'OkHttp|Apache License 2.0',
  'MapLibre Native for Android|BSD 2-Clause License',
  'MapLibre GeoJSON / Turf for Android|MIT License',
  'Timber|Apache License 2.0',
];

function esc(s) {
  return s
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/'/g, "\\'").replace(/"/g, '\\"')
    .replace(/\n/g, '\\n');
}

function build(lang) {
  const out = ['<?xml version="1.0" encoding="utf-8"?>', '<!-- Generated by android/tools/genstrings.js (edit the table there) so English and Gujarati keys always match. -->', '<resources>'];
  if (lang === 'en') {
    for (const [n, v] of FIXED) out.push(`    <string name="${n}" translatable="false">${esc(v)}</string>`);
    out.push('    <string-array name="licenses_list" translatable="false">');
    for (const l of LICENSES) out.push(`        <item>${esc(l)}</item>`);
    out.push('    </string-array>');
  }
  for (const [n, en, gu] of S) {
    const v = lang === 'en' ? en : gu;
    const fmt = /%\d\$[sd]/.test(v) ? '' : (/%/.test(v) ? ' formatted="false"' : '');
    out.push(`    <string name="${n}"${fmt}>${esc(v)}</string>`);
  }
  for (const [n, en, gu] of P) {
    const v = lang === 'en' ? en : gu;
    out.push(`    <plurals name="${n}">`);
    for (const q of ['one', 'other']) out.push(`        <item quantity="${q}">${esc(v[q])}</item>`);
    out.push('    </plurals>');
  }
  out.push('</resources>', '');
  return out.join('\n');
}

fs.writeFileSync(path.join(res, 'values', 'strings.xml'), build('en'));
fs.writeFileSync(path.join(res, 'values-gu', 'strings.xml'), build('gu'));
console.log(`wrote ${S.length} strings, ${P.length} plurals`);
