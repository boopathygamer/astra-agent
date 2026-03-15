"""
App Development Tools — Expert-Level Mobile App Builder.
========================================================
7 registered tools for professional mobile app development:

  app_scaffold_project   — React Native/Flutter/Kotlin/Swift project gen
  app_generate_screen    — Mobile screen/page with navigation & state
  app_generate_api_client— Typed API client (Retrofit/Dio/Axios) with models
  app_build_apk          — Android APK/AAB build via Gradle
  app_manage_dependencies— Add/remove/update packages
  app_generate_assets    — App icons, splash screens, adaptive icons
  app_sign_release       — Signing configs (keystore, provisioning)
"""

import json
import logging
import os
import subprocess
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.tools.registry import registry, ToolRiskLevel

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# React Native Templates
# ══════════════════════════════════════════════════════════════

_RN_TEMPLATE = {
    "App.tsx": textwrap.dedent("""\
        import React from 'react';
        import { NavigationContainer } from '@react-navigation/native';
        import { createNativeStackNavigator } from '@react-navigation/native-stack';
        import HomeScreen from './src/screens/HomeScreen';
        import DetailScreen from './src/screens/DetailScreen';

        const Stack = createNativeStackNavigator();

        export default function App() {
          return (
            <NavigationContainer>
              <Stack.Navigator
                screenOptions={{
                  headerStyle: { backgroundColor: '#1a1a2e' },
                  headerTintColor: '#fff',
                  headerTitleStyle: { fontWeight: '700' },
                }}>
                <Stack.Screen name="Home" component={HomeScreen} />
                <Stack.Screen name="Detail" component={DetailScreen} />
              </Stack.Navigator>
            </NavigationContainer>
          );
        }
    """),
    "src/screens/HomeScreen.tsx": textwrap.dedent("""\
        import React, { useState, useEffect } from 'react';
        import {
          View, Text, FlatList, TouchableOpacity,
          StyleSheet, ActivityIndicator, SafeAreaView,
        } from 'react-native';

        interface Item { id: string; title: string; subtitle: string; }

        export default function HomeScreen({ navigation }: any) {
          const [items, setItems] = useState<Item[]>([]);
          const [loading, setLoading] = useState(true);

          useEffect(() => {
            setTimeout(() => {
              setItems([
                { id: '1', title: 'First Item', subtitle: 'Tap to view details' },
                { id: '2', title: 'Second Item', subtitle: 'Tap to view details' },
              ]);
              setLoading(false);
            }, 500);
          }, []);

          if (loading) return (
            <View style={styles.center}>
              <ActivityIndicator size="large" color="#6366f1" />
            </View>
          );

          return (
            <SafeAreaView style={styles.container}>
              <FlatList
                data={items}
                keyExtractor={(i) => i.id}
                renderItem={({ item }) => (
                  <TouchableOpacity
                    style={styles.card}
                    onPress={() => navigation.navigate('Detail', { item })}
                    activeOpacity={0.7}>
                    <Text style={styles.title}>{item.title}</Text>
                    <Text style={styles.subtitle}>{item.subtitle}</Text>
                  </TouchableOpacity>
                )}
              />
            </SafeAreaView>
          );
        }

        const styles = StyleSheet.create({
          container: { flex: 1, backgroundColor: '#0f172a', padding: 16 },
          center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#0f172a' },
          card: {
            backgroundColor: '#1e293b', borderRadius: 12, padding: 16,
            marginBottom: 12, borderWidth: 1, borderColor: '#334155',
          },
          title: { color: '#f1f5f9', fontSize: 18, fontWeight: '700' },
          subtitle: { color: '#94a3b8', fontSize: 14, marginTop: 4 },
        });
    """),
    "src/screens/DetailScreen.tsx": textwrap.dedent("""\
        import React from 'react';
        import { View, Text, StyleSheet } from 'react-native';

        export default function DetailScreen({ route }: any) {
          const { item } = route.params;
          return (
            <View style={styles.container}>
              <Text style={styles.title}>{item.title}</Text>
              <Text style={styles.body}>{item.subtitle}</Text>
            </View>
          );
        }

        const styles = StyleSheet.create({
          container: { flex: 1, backgroundColor: '#0f172a', padding: 24, justifyContent: 'center' },
          title: { color: '#f1f5f9', fontSize: 28, fontWeight: '800' },
          body: { color: '#94a3b8', fontSize: 16, marginTop: 8 },
        });
    """),
    "src/services/api.ts": textwrap.dedent("""\
        const BASE_URL = 'https://api.example.com';

        class ApiClient {
          private token: string | null = null;

          setToken(token: string) { this.token = token; }

          private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
            const headers: Record<string, string> = {
              'Content-Type': 'application/json',
              ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}),
            };
            const res = await fetch(`${BASE_URL}${endpoint}`, { ...options, headers });
            if (!res.ok) throw new Error(`API Error: ${res.status} ${res.statusText}`);
            return res.json();
          }

          get<T>(endpoint: string) { return this.request<T>(endpoint); }
          post<T>(endpoint: string, data: any) {
            return this.request<T>(endpoint, { method: 'POST', body: JSON.stringify(data) });
          }
          put<T>(endpoint: string, data: any) {
            return this.request<T>(endpoint, { method: 'PUT', body: JSON.stringify(data) });
          }
          delete(endpoint: string) {
            return this.request(endpoint, { method: 'DELETE' });
          }
        }

        export const api = new ApiClient();
    """),
}

_FLUTTER_TEMPLATE = {
    "lib/main.dart": textwrap.dedent("""\
        import 'package:flutter/material.dart';
        import 'screens/home_screen.dart';

        void main() => runApp(const MyApp());

        class MyApp extends StatelessWidget {
          const MyApp({super.key});

          @override
          Widget build(BuildContext context) {
            return MaterialApp(
              title: 'My App',
              debugShowCheckedModeBanner: false,
              theme: ThemeData(
                colorScheme: ColorScheme.dark(
                  primary: const Color(0xFF6366F1),
                  secondary: const Color(0xFFEC4899),
                  surface: const Color(0xFF1E293B),
                ),
                scaffoldBackgroundColor: const Color(0xFF0F172A),
                appBarTheme: const AppBarTheme(
                  backgroundColor: Color(0xFF1E293B),
                  elevation: 0,
                  titleTextStyle: TextStyle(
                    fontSize: 20, fontWeight: FontWeight.w700, color: Colors.white,
                  ),
                ),
                cardTheme: CardTheme(
                  color: const Color(0xFF1E293B),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  elevation: 2,
                ),
                useMaterial3: true,
              ),
              home: const HomeScreen(),
            );
          }
        }
    """),
    "lib/screens/home_screen.dart": textwrap.dedent("""\
        import 'package:flutter/material.dart';

        class HomeScreen extends StatefulWidget {
          const HomeScreen({super.key});
          @override
          State<HomeScreen> createState() => _HomeScreenState();
        }

        class _HomeScreenState extends State<HomeScreen> {
          bool _loading = true;
          final List<Map<String, String>> _items = [];

          @override
          void initState() {
            super.initState();
            _loadData();
          }

          Future<void> _loadData() async {
            await Future.delayed(const Duration(milliseconds: 500));
            setState(() {
              _items.addAll([
                {'title': 'First Item', 'subtitle': 'Tap for details'},
                {'title': 'Second Item', 'subtitle': 'Tap for details'},
              ]);
              _loading = false;
            });
          }

          @override
          Widget build(BuildContext context) {
            return Scaffold(
              appBar: AppBar(title: const Text('My App')),
              body: _loading
                ? const Center(child: CircularProgressIndicator())
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _items.length,
                    itemBuilder: (ctx, i) => Card(
                      margin: const EdgeInsets.only(bottom: 12),
                      child: ListTile(
                        title: Text(_items[i]['title']!,
                          style: const TextStyle(fontWeight: FontWeight.w700)),
                        subtitle: Text(_items[i]['subtitle']!),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () {},
                      ),
                    ),
                  ),
            );
          }
        }
    """),
    "lib/services/api_client.dart": textwrap.dedent("""\
        import 'dart:convert';
        import 'package:http/http.dart' as http;

        class ApiClient {
          static const String baseUrl = 'https://api.example.com';
          String? _token;

          void setToken(String token) => _token = token;

          Map<String, String> get _headers => {
            'Content-Type': 'application/json',
            if (_token != null) 'Authorization': 'Bearer $_token',
          };

          Future<T> get<T>(String endpoint, T Function(dynamic) fromJson) async {
            final res = await http.get(Uri.parse('$baseUrl$endpoint'), headers: _headers);
            if (res.statusCode != 200) throw Exception('API Error: ${res.statusCode}');
            return fromJson(jsonDecode(res.body));
          }

          Future<T> post<T>(String endpoint, Map<String, dynamic> data,
              T Function(dynamic) fromJson) async {
            final res = await http.post(
              Uri.parse('$baseUrl$endpoint'),
              headers: _headers, body: jsonEncode(data),
            );
            if (res.statusCode >= 400) throw Exception('API Error: ${res.statusCode}');
            return fromJson(jsonDecode(res.body));
          }
        }
    """),
}

_KOTLIN_TEMPLATE = {
    "app/src/main/java/com/app/MainActivity.kt": textwrap.dedent("""\
        package com.app

        import android.os.Bundle
        import androidx.activity.ComponentActivity
        import androidx.activity.compose.setContent
        import androidx.compose.foundation.layout.*
        import androidx.compose.material3.*
        import androidx.compose.runtime.*
        import androidx.compose.ui.Modifier
        import androidx.navigation.compose.NavHost
        import androidx.navigation.compose.composable
        import androidx.navigation.compose.rememberNavController

        class MainActivity : ComponentActivity() {
            override fun onCreate(savedInstanceState: Bundle?) {
                super.onCreate(savedInstanceState)
                setContent {
                    MaterialTheme(colorScheme = darkColorScheme()) {
                        val navController = rememberNavController()
                        NavHost(navController, startDestination = "home") {
                            composable("home") { HomeScreen(navController) }
                            composable("detail/{id}") { entry ->
                                DetailScreen(entry.arguments?.getString("id") ?: "")
                            }
                        }
                    }
                }
            }
        }
    """),
    "app/build.gradle.kts": textwrap.dedent("""\
        plugins {
            id("com.android.application")
            id("org.jetbrains.kotlin.android")
        }
        android {
            namespace = "com.app"
            compileSdk = 34
            defaultConfig {
                applicationId = "com.app"
                minSdk = 24
                targetSdk = 34
                versionCode = 1
                versionName = "1.0"
            }
            buildFeatures { compose = true }
            composeOptions { kotlinCompilerExtensionVersion = "1.5.4" }
        }
        dependencies {
            implementation(platform("androidx.compose:compose-bom:2024.01.00"))
            implementation("androidx.compose.material3:material3")
            implementation("androidx.navigation:navigation-compose:2.7.6")
            implementation("androidx.activity:activity-compose:1.8.2")
        }
    """),
}

_SWIFT_TEMPLATE = {
    "MyApp/MyAppApp.swift": textwrap.dedent("""\
        import SwiftUI

        @main
        struct MyAppApp: App {
            var body: some Scene {
                WindowGroup {
                    ContentView()
                }
            }
        }
    """),
    "MyApp/ContentView.swift": textwrap.dedent("""\
        import SwiftUI

        struct ContentView: View {
            @State private var items = [
                ListItem(title: "First Item", subtitle: "Tap for details"),
                ListItem(title: "Second Item", subtitle: "Tap for details"),
            ]

            var body: some View {
                NavigationStack {
                    List(items) { item in
                        NavigationLink(destination: DetailView(item: item)) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(item.title).font(.headline).bold()
                                Text(item.subtitle).font(.subheadline).foregroundColor(.secondary)
                            }.padding(.vertical, 4)
                        }
                    }
                    .navigationTitle("My App")
                    .listStyle(.insetGrouped)
                }
            }
        }

        struct ListItem: Identifiable {
            let id = UUID()
            let title: String
            let subtitle: String
        }

        struct DetailView: View {
            let item: ListItem
            var body: some View {
                VStack { Text(item.title).font(.largeTitle).bold() }
                .navigationTitle(item.title)
            }
        }
    """),
}


# ══════════════════════════════════════════════════════════════
# Tool 1: app_scaffold_project
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="app_scaffold_project",
    description=(
        "Generate a complete mobile app project structure with navigation, "
        "screens, API client, and styling. Supports React Native, Flutter, "
        "Kotlin Compose, and SwiftUI."
    ),
    risk_level=ToolRiskLevel.MEDIUM,
    parameters={
        "project_name": "Project name",
        "platform": "react_native | flutter | kotlin | swift",
        "output_dir": "Output directory",
        "features": "Optional: auth, push_notifications, offline, analytics",
    },
)
def app_scaffold_project(
    project_name: str = "my-app",
    platform: str = "react_native",
    output_dir: str = "",
    features: list = None,
) -> Dict[str, Any]:
    """Scaffold a mobile app project."""
    features = features or []
    templates = {
        "react_native": _RN_TEMPLATE,
        "flutter": _FLUTTER_TEMPLATE,
        "kotlin": _KOTLIN_TEMPLATE,
        "swift": _SWIFT_TEMPLATE,
    }

    if platform not in templates:
        return {"success": False, "error": f"Unknown platform: {platform}. Use: {list(templates.keys())}"}

    project_dir = Path(output_dir) / project_name if output_dir else Path(project_name)
    result = {"success": True, "project_name": project_name, "platform": platform,
              "directory": str(project_dir), "files_created": [], "features": features}

    try:
        for filepath, content in templates[platform].items():
            full_path = project_dir / filepath
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            result["files_created"].append(filepath)

        # Package config
        if platform == "react_native":
            pkg = {
                "name": project_name, "version": "1.0.0", "private": True,
                "dependencies": {
                    "react": "^18.2.0", "react-native": "^0.73.0",
                    "@react-navigation/native": "^6.1.0",
                    "@react-navigation/native-stack": "^6.9.0",
                },
                "devDependencies": {"typescript": "^5.3.0", "@types/react": "^18.2.0"},
            }
            (project_dir / "package.json").write_text(json.dumps(pkg, indent=2), encoding="utf-8")
            result["files_created"].append("package.json")

        elif platform == "flutter":
            pubspec = textwrap.dedent(f"""\
                name: {project_name}
                description: A Flutter application.
                version: 1.0.0+1
                environment:
                  sdk: '>=3.0.0 <4.0.0'
                dependencies:
                  flutter:
                    sdk: flutter
                  http: ^1.1.0
                  provider: ^6.1.0
                dev_dependencies:
                  flutter_test:
                    sdk: flutter
                flutter:
                  uses-material-design: true
            """)
            (project_dir / "pubspec.yaml").write_text(pubspec, encoding="utf-8")
            result["files_created"].append("pubspec.yaml")

        result["message"] = f"App '{project_name}' ({platform}) created with {len(result['files_created'])} files"
    except Exception as e:
        result["success"] = False
        result["error"] = str(e)

    return result


# ══════════════════════════════════════════════════════════════
# Tool 2: app_generate_screen
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="app_generate_screen",
    description=(
        "Generate a mobile screen/page with navigation, state management, "
        "and styled components."
    ),
    risk_level=ToolRiskLevel.LOW,
    parameters={
        "name": "Screen name",
        "platform": "react_native | flutter | kotlin | swift",
        "screen_type": "list | detail | form | settings | profile | dashboard",
        "features": "Optional: pull_refresh, search, pagination, fab",
    },
)
def app_generate_screen(
    name: str = "HomeScreen",
    platform: str = "react_native",
    screen_type: str = "list",
    features: list = None,
) -> Dict[str, Any]:
    """Generate a mobile screen."""
    features = features or []
    generators = {
        "react_native": _gen_rn_screen,
        "flutter": _gen_flutter_screen,
        "kotlin": _gen_kotlin_screen,
        "swift": _gen_swift_screen,
    }

    gen = generators.get(platform)
    if not gen:
        return {"success": False, "error": f"Unsupported platform: {platform}"}

    code = gen(name, screen_type, features)
    ext = {"react_native": "tsx", "flutter": "dart", "kotlin": "kt", "swift": "swift"}
    return {"success": True, "screen_name": name, "platform": platform,
            "filename": f"{name}.{ext[platform]}", "code": code}


def _gen_rn_screen(name, stype, features):
    lines = [
        "import React, { useState, useEffect, useCallback } from 'react';",
        "import { View, Text, FlatList, StyleSheet, RefreshControl, ActivityIndicator } from 'react-native';",
        "",
        f"export default function {name}({{ navigation }}: any) {{",
        "  const [data, setData] = useState<any[]>([]);",
        "  const [loading, setLoading] = useState(true);",
        "  const [refreshing, setRefreshing] = useState(false);",
        "",
        "  const loadData = useCallback(async () => {",
        "    setLoading(true);",
        "    try { /* fetch data */ setData([]); }",
        "    finally { setLoading(false); }",
        "  }, []);",
        "",
        "  useEffect(() => { loadData(); }, [loadData]);",
        "",
    ]
    if "pull_refresh" in features:
        lines.extend([
            "  const onRefresh = async () => {",
            "    setRefreshing(true);",
            "    await loadData();",
            "    setRefreshing(false);",
            "  };",
            "",
        ])
    lines.extend([
        "  return (",
        "    <View style={styles.container}>",
        "      {loading ? <ActivityIndicator size='large' /> : (",
        "        <FlatList data={data} keyExtractor={(i, idx) => String(idx)}",
        "          renderItem={({ item }) => <Text style={styles.item}>{JSON.stringify(item)}</Text>}",
    ])
    if "pull_refresh" in features:
        lines.append("          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}")
    lines.extend([
        "        />",
        "      )}",
        "    </View>",
        "  );",
        "}",
        "",
        "const styles = StyleSheet.create({",
        "  container: { flex: 1, backgroundColor: '#0f172a', padding: 16 },",
        "  item: { color: '#f1f5f9', padding: 12, backgroundColor: '#1e293b', borderRadius: 8, marginBottom: 8 },",
        "});",
    ])
    return "\n".join(lines)


def _gen_flutter_screen(name, stype, features):
    lines = [
        "import 'package:flutter/material.dart';",
        "",
        f"class {name} extends StatefulWidget {{",
        f"  const {name}({{super.key}});",
        f"  @override",
        f"  State<{name}> createState() => _{name}State();",
        "}",
        "",
        f"class _{name}State extends State<{name}> {{",
        "  bool _loading = true;",
        "  List<dynamic> _items = [];",
        "",
        "  @override",
        "  void initState() { super.initState(); _loadData(); }",
        "",
        "  Future<void> _loadData() async {",
        "    setState(() => _loading = true);",
        "    await Future.delayed(const Duration(milliseconds: 500));",
        "    setState(() { _items = []; _loading = false; });",
        "  }",
        "",
        "  @override",
        "  Widget build(BuildContext context) {",
        "    return Scaffold(",
        f"      appBar: AppBar(title: const Text('{name}')),",
        "      body: _loading",
        "        ? const Center(child: CircularProgressIndicator())",
        "        : ListView.builder(",
        "            itemCount: _items.length,",
        "            itemBuilder: (ctx, i) => ListTile(title: Text(_items[i].toString())),",
        "          ),",
        "    );",
        "  }",
        "}",
    ]
    return "\n".join(lines)


def _gen_kotlin_screen(name, stype, features):
    return textwrap.dedent(f"""\
        package com.app.screens

        import androidx.compose.foundation.layout.*
        import androidx.compose.foundation.lazy.LazyColumn
        import androidx.compose.material3.*
        import androidx.compose.runtime.*
        import androidx.compose.ui.Modifier
        import androidx.compose.ui.unit.dp

        @Composable
        fun {name}() {{
            var loading by remember {{ mutableStateOf(true) }}
            val items = remember {{ mutableStateListOf<String>() }}

            LaunchedEffect(Unit) {{
                // Load data
                loading = false
            }}

            if (loading) {{
                Box(Modifier.fillMaxSize(), contentAlignment = androidx.compose.ui.Alignment.Center) {{
                    CircularProgressIndicator()
                }}
            }} else {{
                LazyColumn(modifier = Modifier.fillMaxSize().padding(16.dp)) {{
                    items(items.size) {{ i ->
                        Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {{
                            Text(items[i], modifier = Modifier.padding(16.dp))
                        }}
                    }}
                }}
            }}
        }}
    """)


def _gen_swift_screen(name, stype, features):
    return textwrap.dedent(f"""\
        import SwiftUI

        struct {name}: View {{
            @State private var items: [String] = []
            @State private var isLoading = true

            var body: some View {{
                Group {{
                    if isLoading {{
                        ProgressView()
                    }} else {{
                        List(items, id: \\.self) {{ item in
                            Text(item).font(.body)
                        }}
                    }}
                }}
                .navigationTitle("{name}")
                .task {{ await loadData() }}
            }}

            private func loadData() async {{
                try? await Task.sleep(nanoseconds: 500_000_000)
                items = ["Item 1", "Item 2"]
                isLoading = false
            }}
        }}
    """)


# ══════════════════════════════════════════════════════════════
# Tool 3: app_generate_api_client
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="app_generate_api_client",
    description="Generate a typed API client with models for mobile apps.",
    risk_level=ToolRiskLevel.LOW,
    parameters={
        "base_url": "API base URL",
        "platform": "react_native | flutter | kotlin",
        "endpoints": "List of endpoint configs: [{path, method, name, response_model}]",
    },
)
def app_generate_api_client(
    base_url: str = "https://api.example.com",
    platform: str = "react_native",
    endpoints: list = None,
) -> Dict[str, Any]:
    """Generate a typed API client."""
    endpoints = endpoints or [
        {"path": "/users", "method": "GET", "name": "getUsers"},
        {"path": "/users", "method": "POST", "name": "createUser"},
    ]

    generators = {
        "react_native": _gen_ts_api_client,
        "flutter": _gen_dart_api_client,
        "kotlin": _gen_kotlin_api_client,
    }

    gen = generators.get(platform)
    if not gen:
        return {"success": False, "error": f"Unsupported: {platform}"}

    code = gen(base_url, endpoints)
    ext = {"react_native": "ts", "flutter": "dart", "kotlin": "kt"}
    return {"success": True, "platform": platform, "filename": f"api_client.{ext[platform]}",
            "code": code, "endpoints": len(endpoints)}


def _gen_ts_api_client(base_url, endpoints):
    lines = [
        f"const BASE_URL = '{base_url}';",
        "",
        "class ApiClient {",
        "  private token: string | null = null;",
        "  setToken(t: string) { this.token = t; }",
        "",
        "  private async request<T>(path: string, opts: RequestInit = {}): Promise<T> {",
        "    const res = await fetch(`${BASE_URL}${path}`, {",
        "      ...opts,",
        "      headers: { 'Content-Type': 'application/json',",
        "        ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}) },",
        "    });",
        "    if (!res.ok) throw new Error(`HTTP ${res.status}`);",
        "    return res.json();",
        "  }",
        "",
    ]
    for ep in endpoints:
        method = ep.get("method", "GET").upper()
        name = ep.get("name", "request")
        path = ep.get("path", "/")
        if method == "GET":
            lines.append(f"  {name}() {{ return this.request('{path}'); }}")
        else:
            lines.append(f"  {name}(data: any) {{ return this.request('{path}', {{ method: '{method}', body: JSON.stringify(data) }}); }}")
    lines.extend(["}", "", "export const api = new ApiClient();"])
    return "\n".join(lines)


def _gen_dart_api_client(base_url, endpoints):
    lines = [
        "import 'dart:convert';",
        "import 'package:http/http.dart' as http;",
        "",
        "class ApiClient {",
        f"  static const baseUrl = '{base_url}';",
        "  String? _token;",
        "  void setToken(String t) => _token = t;",
        "  Map<String, String> get _headers => {",
        "    'Content-Type': 'application/json',",
        "    if (_token != null) 'Authorization': 'Bearer $_token',",
        "  };",
        "",
    ]
    for ep in endpoints:
        method = ep.get("method", "GET").upper()
        name = ep.get("name", "request")
        path = ep.get("path", "/")
        if method == "GET":
            lines.append(f"  Future<dynamic> {name}() async {{")
            lines.append(f"    final res = await http.get(Uri.parse('$baseUrl{path}'), headers: _headers);")
            lines.append(f"    return jsonDecode(res.body);")
            lines.append(f"  }}")
        else:
            lines.append(f"  Future<dynamic> {name}(Map<String, dynamic> data) async {{")
            lines.append(f"    final res = await http.{method.lower()}(Uri.parse('$baseUrl{path}'), headers: _headers, body: jsonEncode(data));")
            lines.append(f"    return jsonDecode(res.body);")
            lines.append(f"  }}")
    lines.append("}")
    return "\n".join(lines)


def _gen_kotlin_api_client(base_url, endpoints):
    return textwrap.dedent(f"""\
        import okhttp3.OkHttpClient
        import okhttp3.Request
        import okhttp3.MediaType.Companion.toMediaType
        import okhttp3.RequestBody.Companion.toRequestBody

        class ApiClient {{
            private val client = OkHttpClient()
            private val baseUrl = "{base_url}"
            var token: String? = null

            private fun request(path: String, method: String = "GET", body: String? = null): String {{
                val builder = Request.Builder().url("$baseUrl$path")
                token?.let {{ builder.addHeader("Authorization", "Bearer $it") }}
                if (body != null) builder.method(method, body.toRequestBody("application/json".toMediaType()))
                else builder.method(method, null)
                return client.newCall(builder.build()).execute().body?.string() ?: ""
            }}
        }}
    """)


# ══════════════════════════════════════════════════════════════
# Tool 4: app_build_apk
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="app_build_apk",
    description="Build Android APK/AAB using Gradle or React Native CLI.",
    risk_level=ToolRiskLevel.HIGH,
    parameters={
        "project_dir": "Project root directory",
        "build_type": "debug | release",
        "output_format": "apk | aab",
        "platform": "react_native | flutter | kotlin",
    },
)
def app_build_apk(
    project_dir: str,
    build_type: str = "debug",
    output_format: str = "apk",
    platform: str = "react_native",
) -> Dict[str, Any]:
    """Build Android APK/AAB."""
    if not os.path.isdir(project_dir):
        return {"success": False, "error": f"Directory not found: {project_dir}"}

    cmd_map = {
        "react_native": {
            "apk": ["npx", "react-native", "build-android", f"--mode={build_type}"],
            "aab": ["npx", "react-native", "build-android", "--mode=release", "--tasks=bundleRelease"],
        },
        "flutter": {
            "apk": ["flutter", "build", "apk", f"--{build_type}"],
            "aab": ["flutter", "build", "appbundle", f"--{build_type}"],
        },
        "kotlin": {
            "apk": ["./gradlew", f"assemble{build_type.capitalize()}"],
            "aab": ["./gradlew", f"bundle{build_type.capitalize()}"],
        },
    }

    if platform not in cmd_map:
        return {"success": False, "error": f"Unsupported: {platform}"}

    cmd = cmd_map[platform].get(output_format, cmd_map[platform]["apk"])

    try:
        proc = subprocess.run(cmd, cwd=project_dir, capture_output=True, text=True, timeout=300, shell=False)
        return {
            "success": proc.returncode == 0,
            "command": " ".join(cmd),
            "stdout": proc.stdout[-5000:],
            "stderr": proc.stderr[-2000:],
            "build_type": build_type,
            "output_format": output_format,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Build timed out after 5 minutes"}
    except FileNotFoundError as e:
        return {"success": False, "error": f"Build tool not found: {e}"}


# ══════════════════════════════════════════════════════════════
# Tool 5: app_manage_dependencies
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="app_manage_dependencies",
    description="Add, remove, or update packages in a mobile project.",
    risk_level=ToolRiskLevel.MEDIUM,
    parameters={
        "project_dir": "Project directory",
        "action": "add | remove | update | list",
        "packages": "List of package names",
        "platform": "react_native | flutter | kotlin",
    },
)
def app_manage_dependencies(
    project_dir: str,
    action: str = "list",
    packages: list = None,
    platform: str = "react_native",
) -> Dict[str, Any]:
    """Manage project dependencies."""
    packages = packages or []

    if not os.path.isdir(project_dir):
        return {"success": False, "error": f"Directory not found: {project_dir}"}

    cmd_map = {
        "react_native": {
            "add": ["npm", "install"] + packages,
            "remove": ["npm", "uninstall"] + packages,
            "update": ["npm", "update"] + (packages or []),
            "list": ["npm", "list", "--depth=0"],
        },
        "flutter": {
            "add": ["flutter", "pub", "add"] + packages,
            "remove": ["flutter", "pub", "remove"] + packages,
            "update": ["flutter", "pub", "upgrade"] + (packages or []),
            "list": ["flutter", "pub", "deps"],
        },
    }

    cmds = cmd_map.get(platform)
    if not cmds:
        return {"success": False, "error": f"Unsupported: {platform}"}

    cmd = cmds.get(action)
    if not cmd:
        return {"success": False, "error": f"Unknown action: {action}"}

    try:
        proc = subprocess.run(cmd, cwd=project_dir, capture_output=True, text=True, timeout=120, shell=False)
        return {
            "success": proc.returncode == 0,
            "command": " ".join(cmd),
            "stdout": proc.stdout[-5000:],
            "stderr": proc.stderr[-2000:],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════
# Tool 6: app_generate_assets
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="app_generate_assets",
    description="Generate app icon configs, splash screen configs, and adaptive icon XML.",
    risk_level=ToolRiskLevel.LOW,
    parameters={
        "platform": "android | ios | both",
        "app_name": "Application name",
        "primary_color": "Primary brand color hex",
    },
)
def app_generate_assets(
    platform: str = "both",
    app_name: str = "My App",
    primary_color: str = "#6366F1",
) -> Dict[str, Any]:
    """Generate asset configurations."""
    assets = {"success": True, "files": {}}

    if platform in ("android", "both"):
        # Adaptive icon XML
        assets["files"]["ic_launcher_background.xml"] = textwrap.dedent(f"""\
            <?xml version="1.0" encoding="utf-8"?>
            <shape xmlns:android="http://schemas.android.com/apk/res/android">
                <solid android:color="{primary_color}"/>
            </shape>
        """)
        assets["files"]["colors.xml"] = textwrap.dedent(f"""\
            <?xml version="1.0" encoding="utf-8"?>
            <resources>
                <color name="primary">{primary_color}</color>
                <color name="primary_dark">{primary_color}CC</color>
                <color name="accent">#EC4899</color>
                <color name="splash_bg">{primary_color}</color>
            </resources>
        """)
        assets["files"]["styles.xml"] = textwrap.dedent(f"""\
            <resources>
                <style name="AppTheme" parent="Theme.MaterialComponents.DayNight.NoActionBar">
                    <item name="colorPrimary">@color/primary</item>
                    <item name="colorPrimaryDark">@color/primary_dark</item>
                    <item name="colorAccent">@color/accent</item>
                </style>
                <style name="SplashTheme" parent="AppTheme">
                    <item name="android:windowBackground">@color/splash_bg</item>
                </style>
            </resources>
        """)

    if platform in ("ios", "both"):
        assets["files"]["LaunchScreen.storyboard"] = textwrap.dedent(f"""\
            <?xml version="1.0" encoding="UTF-8"?>
            <document type="com.apple.InterfaceBuilder3.CocoaTouch.Storyboard.XIB" version="3.0">
                <scenes>
                    <scene sceneID="main">
                        <viewController id="vc">
                            <view key="view" contentMode="scaleToFill">
                                <color key="backgroundColor" red="0.388" green="0.4" blue="0.945" alpha="1"/>
                                <subviews>
                                    <label text="{app_name}" textAlignment="center">
                                        <fontDescription key="fontDescription" type="boldSystem" pointSize="32"/>
                                        <color key="textColor" white="1" alpha="1"/>
                                    </label>
                                </subviews>
                            </view>
                        </viewController>
                    </scene>
                </scenes>
            </document>
        """)

    assets["total_files"] = len(assets["files"])
    return assets


# ══════════════════════════════════════════════════════════════
# Tool 7: app_sign_release
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="app_sign_release",
    description="Generate signing configuration for Android keystore or iOS provisioning.",
    risk_level=ToolRiskLevel.MEDIUM,
    parameters={
        "platform": "android | ios",
        "app_name": "Application name",
        "key_alias": "Key alias for signing",
    },
)
def app_sign_release(
    platform: str = "android",
    app_name: str = "my-app",
    key_alias: str = "release-key",
) -> Dict[str, Any]:
    """Generate signing configurations."""
    if platform == "android":
        gradle_signing = textwrap.dedent(f"""\
            android {{
                signingConfigs {{
                    release {{
                        storeFile file("keystore/release.keystore")
                        storePassword System.getenv("KEYSTORE_PASSWORD") ?: ""
                        keyAlias "{key_alias}"
                        keyPassword System.getenv("KEY_PASSWORD") ?: ""
                    }}
                }}
                buildTypes {{
                    release {{
                        signingConfig signingConfigs.release
                        minifyEnabled true
                        proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
                    }}
                }}
            }}
        """)
        keytool_cmd = (
            f'keytool -genkey -v -keystore release.keystore '
            f'-alias {key_alias} -keyalg RSA -keysize 2048 -validity 10000'
        )
        return {
            "success": True, "platform": "android",
            "gradle_config": gradle_signing,
            "keytool_command": keytool_cmd,
            "instructions": [
                f"1. Run: {keytool_cmd}",
                "2. Add gradle_config to app/build.gradle",
                "3. Set env vars: KEYSTORE_PASSWORD, KEY_PASSWORD",
                "4. Build: ./gradlew assembleRelease",
            ],
        }

    elif platform == "ios":
        return {
            "success": True, "platform": "ios",
            "instructions": [
                "1. Open Xcode > Project > Signing & Capabilities",
                "2. Select your Apple Developer Team",
                "3. Enable 'Automatically manage signing'",
                "4. Create App ID in Apple Developer portal",
                "5. Create provisioning profile for distribution",
                "6. Archive: Product > Archive > Distribute App",
            ],
            "export_plist": textwrap.dedent("""\
                <?xml version="1.0" encoding="UTF-8"?>
                <plist version="1.0"><dict>
                    <key>method</key><string>app-store</string>
                    <key>teamID</key><string>YOUR_TEAM_ID</string>
                    <key>uploadSymbols</key><true/>
                    <key>compileBitcode</key><false/>
                </dict></plist>
            """),
        }

    return {"success": False, "error": f"Unsupported platform: {platform}"}
