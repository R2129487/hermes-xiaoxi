/// 用户模型 — 对应后端 _safe_user
class User {
  final String id;
  final String username;
  final String displayName;
  final String role;
  final String createdAt;

  User({
    required this.id,
    required this.username,
    this.displayName = '',
    this.role = 'operator',
    this.createdAt = '',
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'] ?? '',
      username: json['username'] ?? '',
      displayName: json['display_name'] ?? '',
      role: json['role'] ?? 'operator',
      createdAt: json['created_at'] ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'username': username,
    'display_name': displayName,
    'role': role,
    'created_at': createdAt,
  };
}
