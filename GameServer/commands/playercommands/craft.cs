using System.Collections.Generic;
using DOL.Database;
using DOL.GS.Keeps;

namespace DOL.GS.Commands
{
    [CmdAttribute(
        "&craftmacro",
        ePrivLevel.Player,
        "Crafting macros and utilities",
        "'/craftmacro set <#>' to set how many items you want to craft",
        "'/craftmacro clear' to reset to crafting once",
        "'/craftmacro show' to show the current craft settings",
        "'/craftmacro buy' to buy the necessary materials to craft one item",
        "'/craftmacro buy <#>' to buy the necessary materials to craft <#> items",
        "'/craftmacro buyto <#>' to buy only the missing materials to craft <#> items")]
    public class CraftMacroCommandHandler : AbstractCommandHandler, ICommandHandler
    {
        public void OnCommand(GameClient client, string[] args)
        {
            if (args.Length >= 2)
            {
                #region set

                if (args[1] == "set")
                {
                    if (args.Length >= 3)
                    {
                        int.TryParse(args[2], out int count);
                        if (count == 0)
                        {
                            DisplayMessage(client, T(client, "PlayerCommands.CraftMacro.UseSet"));
                            return;
                        }

                        if (count > 100)
                        {
                            count = 100;
                        }

                        client.Player.TempProperties.SetProperty(CraftAction.CRAFT_QUEUE_LENGTH_PROPERTY, count);
                        DisplayMessage(client, T(client, "PlayerCommands.CraftMacro.QueueSetItems", count));
                    }
                    else
                    {
                        DisplayMessage(client, T(client, "PlayerCommands.CraftMacro.UseSet"));
                    }
                }

                #endregion

                #region clear

                if (args[1] == "clear")
                {

                    client.Player.TempProperties.RemoveProperty(CraftAction.CRAFT_QUEUE_LENGTH_PROPERTY);

                    var recipe = client.Player.TempProperties.GetProperty<Recipe>(CraftAction.RECIPE_TO_CRAFT_PROPERTY);
                    if (recipe != null)
                    {
                        client.Player.TempProperties.RemoveProperty(CraftAction.RECIPE_TO_CRAFT_PROPERTY);
                    }

                    DisplayMessage(client, T(client, "PlayerCommands.CraftMacro.QueueReset"));
                }

                #endregion

                #region show

                if (args[1] == "show")
                {
                    if (client.Player.TempProperties.GetProperty<int>(CraftAction.CRAFT_QUEUE_LENGTH_PROPERTY) != 0)
                        DisplayMessage(client,
                            T(client, "PlayerCommands.CraftMacro.QueueSet", client.Player.TempProperties.GetProperty<int>(CraftAction.CRAFT_QUEUE_LENGTH_PROPERTY)));
                    else
                        DisplayMessage(client, T(client, "PlayerCommands.CraftMacro.QueueSet", 1));
                }

                #endregion

                #region buy

                if (args[1] == "buy")
                {
                    int amount = 1;
                    if (args.Length >= 3)
                    {
                        int.TryParse(args[2], out amount);
                        if (amount == 0)
                        {
                            amount = 1;
                        }
                    }

                    var recipe = client.Player.TempProperties.GetProperty<Recipe>(CraftAction.RECIPE_TO_CRAFT_PROPERTY);
                    if (recipe != null)
                    {
                        if (client.Player.TargetObject is GameMerchant merchant)
                        {
                            var merchantitems = DOLDB<DbMerchantItem>.SelectObjects(DB.Column("ItemListID")
                                .IsEqualTo(merchant.TradeItems.ItemsListID));

                            IList<Ingredient> recipeIngredients;

                            lock (recipe.Lock)
                            {
                                recipeIngredients = recipe.Ingredients;
                            }

                            foreach (var ingredient in recipeIngredients)
                            {
                                foreach (var items in merchantitems)
                                {
                                    var item =
                                        GameServer.Database.FindObjectByKey<DbItemTemplate>(items.ItemTemplateID);
                                    if (item != ingredient.Material) continue;
                                    merchant.OnPlayerBuy(client.Player, items.SlotPosition, items.PageNumber,
                                        ingredient.Count * amount);
                                }
                            }

                            return;
                        }
                        else if (client.Player.TargetObject is GameGuardMerchant guardMerchant)
                        {
                            var merchantitems = DOLDB<DbMerchantItem>.SelectObjects(DB.Column("ItemListID")
                                .IsEqualTo(guardMerchant.TradeItems.ItemsListID));

                            IList<Ingredient> recipeIngredients;

                            lock (recipe.Lock)
                            {
                                recipeIngredients = recipe.Ingredients;
                            }

                            foreach (var ingredient in recipeIngredients)
                            {
                                foreach (var items in merchantitems)
                                {
                                    var item =
                                        GameServer.Database.FindObjectByKey<DbItemTemplate>(items.ItemTemplateID);
                                    if (item != ingredient.Material) continue;
                                    guardMerchant.OnPlayerBuy(client.Player, items.SlotPosition, items.PageNumber,
                                        ingredient.Count * amount);
                                }
                            }

                            return;
                        }
                        DisplayMessage(client, T(client, "PlayerCommands.CraftMacro.TargetMerchant"));
                        return;
                    }

                    DisplayMessage(client, T(client, "PlayerCommands.CraftMacro.NoRecipe"));
                }

                #endregion

                #region buyto

                if (args[1] == "buyto")
                {
                    if (args.Length < 3)
                    {
                        DisplayMessage(client, T(client, "PlayerCommands.CraftMacro.UseBuyTo"));
                        return;
                    }

                    if (int.TryParse(args[2], out int amount))
                    {
                        if (amount == 0)
                        {
                            amount = 1;
                        }
                    }
                    else
                    {
                        DisplayMessage(client, T(client, "PlayerCommands.CraftMacro.UseBuyTo"));
                        return;
                    }

                    var recipe = client.Player.TempProperties.GetProperty<Recipe>(CraftAction.RECIPE_TO_CRAFT_PROPERTY);
                    if (recipe != null)
                    {
                        if (client.Player.TargetObject is GameMerchant merchant)
                        {
                            var merchantitems = DOLDB<DbMerchantItem>.SelectObjects(DB.Column("ItemListID")
                                .IsEqualTo(merchant.TradeItems.ItemsListID));

                            IList<Ingredient> recipeIngredients;

                            lock (recipe.Lock)
                            {
                                recipeIngredients = recipe.Ingredients;
                            }

                            var playerItems = new List<DbInventoryItem>();

                            lock (client.Player.Inventory.Lock)
                            {
                                foreach (var pItem in client.Player.Inventory.AllItems)
                                {
                                    if (pItem.SlotPosition < (int)eInventorySlot.FirstBackpack ||
                                        pItem.SlotPosition > (int)eInventorySlot.LastBackpack)
                                        continue;
                                    playerItems.Add(pItem);
                                }
                            }

                            foreach (var ingredient in recipeIngredients)
                            {
                                foreach (var items in merchantitems)
                                {
                                    var item =
                                        GameServer.Database.FindObjectByKey<DbItemTemplate>(items.ItemTemplateID);
                                    if (item != ingredient.Material) continue;
                                    int playerAmount = 0;

                                    foreach (var pItem in playerItems)
                                    {
                                        if (pItem.Template == ingredient.Material)
                                            playerAmount += pItem.Count;
                                    }

                                    merchant.OnPlayerBuy(client.Player, items.SlotPosition, items.PageNumber,
                                        (ingredient.Count * amount) - playerAmount);
                                }
                            }

                            DisplayMessage(client, T(client, "PlayerCommands.CraftMacro.BoughtItems", amount, recipe.Product.Name));
                            return;
                        }

                        DisplayMessage(client, T(client, "PlayerCommands.CraftMacro.TargetMerchant"));
                        return;
                    }

                    DisplayMessage(client, T(client, "PlayerCommands.CraftMacro.NoRecipe"));
                }

                #endregion
            }
            else
            {
                DisplaySyntax(client);
            }
        }
    }
}
