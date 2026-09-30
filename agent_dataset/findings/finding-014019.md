---
id: 14019
severity: "High"
---

# Malicious User Could Burn The Assets After A Successful Migration

## Description

The following describes the migration process for a vault.

1. Assume that Alice is the proposer.
2. Alice calls `Migration.propose` to propose a set of modules and plugins to migrate a vault to
3. Other contributors could join a migration proposal by contributing ether and fractional tokens by calling `Migration.join`.
4. Alice calls `Migration.commit` to kick off the buyout process for a migration after the proposal period (7 days)
5. If the buyout is successful, Alice calls the `Migration.settleVault` to settle a migration. Within this function, a new vault with new set permissions and plugins will be deployed.
6. Alice calls the `Migration.settleFractions` to mint the fractional tokens for a new vault.
7. Contributors who earlier joined the migration proposal could call the `Migration.migrateFractions` to migrate their fractional tokens from the old vault to the new vault.
8. Finally, Alice will call `Migration.migrateVaultERC20`, `Migration.migrateVaultERC721`, and/or `Migration.migrateVaultERC1155` to transfer the ERC20, ERC721 (NFT), and/or ERC1155 tokens from the old vault to the new vault.

It was observed that after a successful vault migration, an attacker could [`Migration.migrateVaultERC20`](https://github.com/code-423n4/2022-07-fractional/blob/8f2697ae727c60c93ea47276f8fa128369abfe51/src/modules/Migration.sol#L334), [`Migration.migrateVaultERC721`](https://github.com/code-423n4/2022-07-fractional/blob/8f2697ae727c60c93ea47276f8fa128369abfe51/src/modules/Migration.sol#L358), and/or [`Migration.migrateVaultERC1155`](https://github.com/code-423n4/2022-07-fractional/blob/8f2697ae727c60c93ea47276f8fa128369abfe51/src/modules/Migration.sol#L383) with an invalid `_proposalId` parameter, causing the assets within the vault to be burned.

Loss of assets for the users as the assets that they own can be burned by an attacker after a successful migration.

## Proof of Concept

The PoC for `Migration.migrateVaultERC20`, `Migration.migrateVaultERC721`, and/or `Migration.migrateVaultERC1155` is the same. Thus, only the PoC for `Migration.migrateVaultERC721` is shown below, and the PoC for `migrateVaultERC20` and `migrateVaultERC1155` are omitted for brevity.

Assume that the following:

* `vault A` holds only one (1) APE ERC721 NFT
* Alice proposes to migrate `vault A` to a new vault, and the buyout is successful.
* Alice proceeds to call `Migration.settleVault` to settle a migration, followed by `Migration.settleFractions` to mint the fractional tokens for a new vault.
* An attacker calls `Migration.migrateVaultERC721(vault A, invalid_proposal_id, ape_nft_address, ape_nft_tokenId, erc721TransferProof)` with an invalid proposal ID (proposal ID that does not exist).

  * Within the `Migration.migrateVaultERC721` function, the `newVault = migrationInfo[_vault][_proposalId].newVault` will evaluate to zero. This is because the `_proposalId` is a non-existent index in the `migrationInfo` array, so it will point to an address space that has not been initialised yet. Thus, the value `zero` will be returned, and `newVault` will be set to `address(0)`.
* Next, the `Migration.migrateVaultERC721` function will attempt to transfer the ERC721 NFT from the old vault (`_vault`) to the new vault (`newVault`) by calling `IBuyout(buyout).withdrawERC721`. Since `newVault` is set to `address(0)`, this will cause the ERC721 NFT to be sent to `address(0)`, which effectively burns the NFT.

```solidity
/// @notice Migrates an ERC-721 token to the new vault after a successful migration
/// @param _vault Address of the vault
/// @param _proposalId ID of the proposal
/// @param _token Address of the ERC-721 token
/// @param _tokenId ID of the token
/// @param _erc721TransferProof Merkle proof for transferring an ERC-721 token
function migrateVaultERC721(
    address _vault,
    uint256 _proposalId,
    address _token,
    uint256 _tokenId,
    bytes32[] calldata _erc721TransferProof
) external {
    address newVault = migrationInfo[_vault][_proposalId].newVault;
    // Withdraws an ERC-721 token from the old vault and transfers to the new vault
    IBuyout(buyout).withdrawERC721(
        _vault,
        _token,
        newVault,
        _tokenId,
        _erc721TransferProof
    );
}
```

## Recommendation

It is recommended to implement additional validation to ensure that the `_proposalId` submitted is valid.

Consider checking if `newVault` points to a valid vault address before transferring the assets from old vault to new vault.

```solidity
function migrateVaultERC721(
    address _vault,
    uint256 _proposalId,
    address _token,
    uint256 _tokenId,
    bytes32[] calldata _erc721TransferProof
) external {
    address newVault = migrationInfo[_vault][_proposalId].newVault;
    if (newVault == address(0)) reverts VaultDoesNotExistOrInvalid;
    
    // Withdraws an ERC-721 token from the old vault and transfers to the new vault
    IBuyout(buyout).withdrawERC721(
        _vault,
        _token,
        newVault,
        _tokenId,
        _erc721TransferProof
    );
}
```

In the above implementation, if anyone attempts to submit an invalid `_proposalId`, the `newVault` will be set to address(0). The newly implemented validation will detect the abnormal behavior and revert the transaction.

For defense-in-depth, perform additional validation to ensure that the `_to` address is not `address(0)` within the `Buyout.withdrawERC721` function.

```solidity
function withdrawERC721(
    address _vault,
    address _token,
    address _to,
    uint256 _tokenId,
    bytes32[] calldata _erc721TransferProof
) external {
    // Reverts if address is not a registered vault
    (, uint256 id) = IVaultRegistry(registry).vaultToToken(_vault);
    if (id == 0) revert NotVault(_vault);
    if (_to == 0) revert ToAddressIsZero(); 
    // Reverts if auction state is not successful
    (, address proposer, State current, , , ) = this.buyoutInfo(_vault);
    State required = State.SUCCESS;
    if (current != required) revert InvalidState(required, current);
    // Reverts if caller is not the auction winner
    if (msg.sender != proposer) revert NotWinner();

    // Initializes vault transaction
    bytes memory data = abi.encodeCall(
        ITransfer.ERC721TransferFrom,
        (_token, _vault, _to, _tokenId)
    );
    // Executes transfer of ERC721 token to caller
    IVault(payable(_vault)).execute(transfer, data, _erc721TransferProof);
}
```

The same validation checks should be implemented on `migrateVaultERC20`, `migrateVaultERC1155`, `withdrawERC20` and `withdrawERC1155`

`migrateVaultERC20` could transfer assets to address(0). ERC721 and 1155 standards require revert when to is address(0), but this is not required by the ERC20 standard. This could be triggered by calling migrate with an invalid `proposalId`. Agree this is a High risk issue.

Selecting this submission as the primary report for clearly outlining the potential high risk scenario here.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability concerns the migration workflow of a vault that allows assets to be moved from an old vault to a newly created vault after a successful buyout. The core of the issue lies in the functions Migration.migrateVaultERC20, Migration.migrateVaultERC721, and Migration.migrateVaultERC1155, which accept a proposal identifier (_proposalId) but do not verify that the identifier corresponds to an existing migration proposal. When an attacker supplies an invalid or non‑existent _proposalId, the internal lookup migrationInfo[_vault][_proposalId] returns a default struct whose newVault field is the zero address. The functions then pass this zero address to the Buyout.withdraw* routines, which consequently transfer the selected asset—whether an ERC‑20 token, an ERC‑721 NFT, or an ERC‑1155 token—to address(0). Transferring to the zero address effectively burns the asset, removing it permanently from circulation. Because the withdraw functions do not contain a guard against a zero destination address, the transaction succeeds without reverting, and no explicit error is emitted. The exploit can be carried out by any user after the migration has been settled; no special permissions are required to invoke the migrateVault* functions. From a user’s perspective, assets that were expected to appear in the new vault simply vanish; a user may look at the UI and see that their NFT or token balance is now zero despite a successful migration, leading to confusion and loss of funds. The flaw was discovered during a manual audit of the migration contract where the lack of validation for the proposal identifier and the absence of a zero‑address check in the asset withdrawal path were observed. This type of bug belongs to the broader class of ‘uninitialized or null‑address transfer’ vulnerabilities, where missing input validation allows funds to be sent to an unrecoverable address. The impact is severe: users lose ownership of their assets, which defeats the fundamental accounting guarantees of the protocol. To remediate the issue, the contract should enforce that the supplied _proposalId maps to a valid migration entry and that the derived newVault address is not address(0). Additionally, the withdrawal functions in the Buyout contract should reject any transfer where the destination address is zero, reverting with a clear error. Implementing these checks will prevent malicious actors from directing assets to the burn address and restore confidence that the migration process respects the intended asset flow.
