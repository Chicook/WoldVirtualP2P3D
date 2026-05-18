using System;
using Microsoft.Data.Sqlite;
using System.IO;
using System.Collections.Generic;

namespace VisorSingularity
{
    public class DatabaseManager
    {
        private string _dbPath;

        public DatabaseManager(string dbFolder = "Data")
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string fullDbFolder = Path.Combine(baseDir, dbFolder);
            
            if (!Directory.Exists(fullDbFolder)) 
                Directory.CreateDirectory(fullDbFolder);

            _dbPath = Path.Combine(fullDbFolder, "wold_core.db");
            InitializeDatabase();
        }

        private void InitializeDatabase()
        {
            using (var connection = new SqliteConnection($"Data Source={_dbPath}"))
            {
                connection.Open();
                
                using (var pragmaCmd = connection.CreateCommand())
                {
                    pragmaCmd.CommandText = "PRAGMA journal_mode=WAL;";
                    pragmaCmd.ExecuteNonQuery();
                }

                var command = connection.CreateCommand();
                command.CommandText = @"
                    CREATE TABLE IF NOT EXISTS Users (
                        Id TEXT PRIMARY KEY,
                        Username TEXT UNIQUE,
                        PasswordHash TEXT,
                        HardwareHash TEXT UNIQUE,
                        WalletAddress TEXT,
                        IslandId TEXT,
                        RegistrationDate DATETIME
                    );
                ";
                command.ExecuteNonQuery();
            }
        }

        public bool CheckHardwareExists(string hardwareHash, out string? existingUsername)
        {
            existingUsername = null;
            using (var connection = new SqliteConnection($"Data Source={_dbPath}"))
            {
                connection.Open();
                var command = connection.CreateCommand();
                command.CommandText = "SELECT Username FROM Users WHERE HardwareHash = @hash";
                command.Parameters.AddWithValue("@hash", hardwareHash);

                using (var reader = command.ExecuteReader())
                {
                    if (reader.Read())
                    {
                        existingUsername = reader.GetString(0);
                        return true;
                    }
                }
            }
            return false;
        }

        public void RegisterUser(string username, string password, string hardwareHash, string islandId)
        {
            using (var connection = new SqliteConnection($"Data Source={_dbPath}"))
            {
                connection.Open();
                var command = connection.CreateCommand();
                command.CommandText = @"
                    INSERT INTO Users (Id, Username, PasswordHash, HardwareHash, IslandId, RegistrationDate)
                    VALUES (@id, @user, @pass, @hhash, @island, @date)
                ";
                command.Parameters.AddWithValue("@id", Guid.NewGuid().ToString());
                command.Parameters.AddWithValue("@user", username);
                command.Parameters.AddWithValue("@pass", password); 
                command.Parameters.AddWithValue("@hhash", hardwareHash);
                command.Parameters.AddWithValue("@island", islandId);
                command.Parameters.AddWithValue("@date", DateTime.Now);
                command.ExecuteNonQuery();
            }
        }
        
        public void UpdateWallet(string username, string wallet)
        {
            using (var connection = new SqliteConnection($"Data Source={_dbPath}"))
            {
                connection.Open();
                var command = connection.CreateCommand();
                command.CommandText = "UPDATE Users SET WalletAddress = @wallet WHERE Username = @user";
                command.Parameters.AddWithValue("@wallet", wallet);
                command.Parameters.AddWithValue("@user", username);
                command.ExecuteNonQuery();
            }
        }

        public void UpdateUserIsland(string username, string islandId)
        {
            using (var connection = new SqliteConnection($"Data Source={_dbPath}"))
            {
                connection.Open();
                var command = connection.CreateCommand();
                command.CommandText = "UPDATE Users SET IslandId = @island WHERE Username = @user";
                command.Parameters.AddWithValue("@island", islandId);
                command.Parameters.AddWithValue("@user", username);
                command.ExecuteNonQuery();
            }
        }

        public bool ValidateLogin(string username, string password, string hardwareHash, out string? islandId, out string? wallet)
        {
            islandId = null;
            wallet = null;
            using (var connection = new SqliteConnection($"Data Source={_dbPath}"))
            {
                connection.Open();
                var command = connection.CreateCommand();
                command.CommandText = "SELECT IslandId, WalletAddress FROM Users WHERE Username = @user AND PasswordHash = @pass AND HardwareHash = @hhash";
                command.Parameters.AddWithValue("@user", username);
                command.Parameters.AddWithValue("@pass", password);
                command.Parameters.AddWithValue("@hhash", hardwareHash);

                using (var reader = command.ExecuteReader())
                {
                    if (reader.Read())
                    {
                        islandId = reader.IsDBNull(0) ? null : reader.GetString(0);
                        wallet = reader.IsDBNull(1) ? null : reader.GetString(1);
                        return true;
                    }
                }
            }
            return false;
        }

        public string GetUserIsland(string username)
        {
            using (var connection = new SqliteConnection($"Data Source={_dbPath}"))
            {
                connection.Open();
                var command = connection.CreateCommand();
                command.CommandText = "SELECT IslandId FROM Users WHERE Username = @user";
                command.Parameters.AddWithValue("@user", username);
                var result = command.ExecuteScalar();
                return result?.ToString() ?? "137 : 190.1.0";
            }
        }

        public List<(string Username, string IslandId)> GetAllUsersAndIslands()
        {
            var list = new List<(string Username, string IslandId)>();
            using (var connection = new SqliteConnection($"Data Source={_dbPath}"))
            {
                connection.Open();
                var command = connection.CreateCommand();
                command.CommandText = "SELECT Username, IslandId FROM Users WHERE IslandId IS NOT NULL AND IslandId != ''";
                using (var reader = command.ExecuteReader())
                {
                    while (reader.Read())
                    {
                        string user = reader.GetString(0);
                        string island = reader.GetString(1);
                        list.Add((user, island));
                    }
                }
            }
            return list;
        }
    }
}
